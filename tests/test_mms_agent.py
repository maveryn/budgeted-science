"""Offline-only MMS Luna adapter/campaign tests; no credentials or network."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents import mms_catalog as campaign
from budgeted_science.agents import mms_verification as agent
from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.agents.runner import run_episode
from budgeted_science.agents.verification_incremental_catalog import BatchBudget
from budgeted_science.mms_verification.environment import Audit
from budgeted_science.mms_verification.experiment import run_cpu


class MMSAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_root = tempfile.TemporaryDirectory()
        cls.catalog_path = run_cpu(cls.fixture_root.name)
        cls.cases, cls.comparisons, cls.source = campaign.read_catalog(cls.catalog_path)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_root.cleanup()

    def instance(self, index=0):
        case = deepcopy(self.cases[index])
        return agent.MMSInstance(case, deepcopy(self.comparisons[case["id"]]), deepcopy(self.source))

    def episode(self, directory):
        log = RunLog(directory, "fixture")
        self.addCleanup(log.close)
        return agent.MMSEpisode(agent.MMSConfig(), self.instance(), log)

    def test_frozen_settings(self):
        for values in ({"model":"gpt-5.6-sol"}, {"reasoning_effort":"low"}, {"scientific_budget":20},
                       {"api_ceiling_usd":"3"}, {"max_output_tokens":8192}, {"deadline_seconds":1200}):
            with self.assertRaises(ValueError):
                replace(agent.MMSConfig(), **values)

    def test_no_hidden_or_policy_information_in_public_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = self.episode(tmp)
            public = json.dumps([agent.prompts(episode.config, episode), agent.tool_definitions(),
                                 episode.execute("r", "record", '{"result_id":"original"}')])
            for forbidden in ('"private"', '"reference_q"', '"q_error"', '"category"', '"flavor"',
                              '"qoi_truth"', '"order_truth"', 'study_aware', 'early_reject', '8.8166',
                              'first-order upwind', 'study_profile'):
                self.assertNotIn(forbidden, public)
            episode.log.close()

    def test_same_science_and_charging(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = self.episode(tmp)
            args = {"grid":16, "family":"mixed", "kernel":"audited"}
            output = episode.execute("c", "run_mms", json.dumps(args))
            reference = Audit(self.cases[0], 10).call("c", "run_mms", **args)
            for key in ("q", "grid", "charge", "diagnostic_errors"):
                self.assertEqual(output["result"][key], reference["result"][key])
            self.assertEqual(output["budget_after"]["spent"], 1)
            episode.log.close()

    def test_invalid_arguments_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = self.episode(tmp)
            for index, args in enumerate(({"grid":True,"kernel":"audited"}, {"grid":8,"kernel":"exact"},
                                           {"grid":16,"kernel":"audited","extra":1})):
                self.assertFalse(episode.execute(str(index), "run_study", json.dumps(args))["ok"])
            self.assertEqual(episode.environment.status()["spent"], 0)
            episode.log.close()

    def test_dedup_retrieval_and_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = self.episode(tmp)
            args = '{"grid":16,"kernel":"independent"}'
            result = episode.execute("c", "run_study", args)
            self.assertEqual(episode.execute("c", "run_study", args), result)
            self.assertFalse(episode.execute("c", "budget", "{}")["ok"])
            record = episode.execute("r", "record", '{"result_id":"run-001"}')
            self.assertEqual(len(record["result"]["field"]), 17)
            self.assertEqual(episode.environment.status()["spent"], 1)
            episode.log.close()

    def test_exhaustion_keeps_submission_possible(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = self.episode(tmp)
            self.assertFalse(episode.execute("c", "run_study", '{"grid":64,"kernel":"audited"}')["ok"])
            args = {"qoi":"ABSTAIN","order":"ABSTAIN","evidence_ids":[],"explanation":"Insufficient evidence."}
            self.assertTrue(episode.execute("s", "submit", json.dumps(args))["ok"])
            self.assertTrue(episode.evaluate()["complete"])
            self.assertFalse(episode.evaluate()["joint_correct"])
            episode.log.close()

    def test_unknown_evidence_does_not_submit(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = self.episode(tmp)
            args = {"qoi":"ACCEPT","order":"ACCEPT","evidence_ids":["unknown"],"explanation":"x"}
            self.assertFalse(episode.execute("s", "submit", json.dumps(args))["ok"])
            self.assertIsNone(episode.submission)
            episode.log.close()

    def test_separate_scores_and_no_evaluator_in_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = RunLog(tmp, "fixture")
            self.addCleanup(log.close)
            episode = agent.MMSEpisode(agent.MMSConfig(), self.instance(4), log)
            args = {"qoi":"ACCEPT","order":"REJECT","evidence_ids":[],"explanation":"Fixture."}
            result = episode.execute("s", "submit", json.dumps(args))
            self.assertNotIn("truth", json.dumps(result))
            self.assertTrue(episode.evaluate()["joint_correct"])
            episode.log.close()

    def test_logged_episode_and_replay_without_key(self):
        with tempfile.TemporaryDirectory() as tmp, patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("key")):
            gateway = agent.MMSGateway()
            path, reason = asyncio.run(run_episode(campaign.ROOT, Path(tmp), mode="dry-run", config=agent.MMSConfig(),
                                                   instance=self.instance(), adapter=agent.MMSAdapter(), gateway=gateway))
            self.assertEqual(reason, "submitted")
            self.assertEqual(len(gateway.requests), 3)
            self.assertEqual(gateway.requests[0]["reasoning"], {"effort":"high","summary":"auto"})
            self.assertFalse(gateway.requests[0]["parallel_tool_calls"])
            self.assertTrue(any(i.get("encrypted_content") == "opaque-fixture" for i in gateway.requests[1]["input"]))
            before = (path/"transcript.md").read_bytes()
            with patch.object(Audit, "call", side_effect=AssertionError("reran tools")):
                agent.regenerate(path)
            self.assertEqual(before, (path/"transcript.md").read_bytes())
            self.assertFalse(read_events(path)[1])

    def test_uncertain_stream_retains_reservation(self):
        class Broken(agent.MMSGateway):
            async def stream(self, body, metadata):
                yield {"type":"response.output_text.delta", "delta":"partial"}
                raise OSError("synthetic disconnection")
        with tempfile.TemporaryDirectory() as tmp:
            path, reason = asyncio.run(run_episode(campaign.ROOT, Path(tmp), mode="dry-run", config=agent.MMSConfig(),
                                                   instance=self.instance(), adapter=agent.MMSAdapter(), gateway=Broken()))
            result = json.loads((path/"evaluation.json").read_text())
            self.assertEqual(reason, "request_or_runner_error")
            self.assertGreater(float(result["api_budget"]["uncertain_reserved_usd"]), 0)
            self.assertFalse(result["evaluation"]["complete"])
            self.assertIn("partial", (path/"transcript.md").read_text())

    def test_nullable_reasoning_content_is_replayable(self):
        class Nullable(agent.MMSGateway):
            async def stream(self, body, metadata):
                async for event in super().stream(body, metadata):
                    if event["type"] == "response.completed":
                        for item in event["response"]["output"]:
                            if item["type"] == "reasoning":
                                item["content"] = None
                    yield event
        with tempfile.TemporaryDirectory() as tmp:
            path, reason = asyncio.run(run_episode(campaign.ROOT, Path(tmp), mode="dry-run", config=agent.MMSConfig(),
                                                   instance=self.instance(), adapter=agent.MMSAdapter(), gateway=Nullable()))
            self.assertEqual(reason, "submitted")
            result = json.loads((path/"evaluation.json").read_text())
            self.assertTrue(result["evaluation"]["complete"])

    def test_batch_maximum_and_no_repeat(self):
        money = BatchBudget("2")
        money.reserve(0, .01, "2")
        self.assertEqual(money.status()["remaining_usd"], "0")
        with self.assertRaises(ValueError):
            money.reserve(0, .01, "2")

    def test_whole_offline_batch_and_integrity(self):
        with tempfile.TemporaryDirectory() as tmp, patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("key")):
            path = asyncio.run(campaign.run_catalog(catalog_path=self.catalog_path, output_root=Path(tmp), mode="dry-run"))
            summary = campaign.render(path)
            self.assertEqual(summary["finished_attempts"], 6)
            self.assertEqual(summary["complete"], 6)
            self.assertEqual(summary["joint_correct"], 0)  # Deliberate scripted abstentions.
            self.assertLess(float(summary["batch_budget"]["committed_upper_usd"]), 2)
            self.assertEqual(len(list((path/"slots").glob("*.json"))), 6)
            with patch.object(Audit, "call", side_effect=AssertionError("tool on replay")):
                campaign.render(path)
            first = next((path/"results").glob("*.json"))
            first.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "integrity"):
                campaign.render(path)


if __name__ == "__main__":
    unittest.main()

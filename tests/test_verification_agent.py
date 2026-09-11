"""Offline adapter, end-to-end runner and explicit-resume verification."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents.records import RunLog, digest, read_events
from budgeted_science.agents.runner import run_episode, StopEpisode
from budgeted_science.agents.verification import (
    VerificationAdapter, VerificationConfig, VerificationEpisode, VerificationInstance,
    prompts, tool_definitions)
from budgeted_science.agents.verification_fake import VerificationGateway
from budgeted_science.agents.verification_reporting import regenerate
from budgeted_science.agents.verification_resume import prepare_resume
from test_claim_verification import examples

ROOT = Path(__file__).resolve().parents[1]


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = RunLog(self.tmp.name, "test")
        self.config = VerificationConfig()
        self.instance = VerificationInstance(examples()[0])
        self.episode = VerificationEpisode(self.config, self.instance, self.log)

    def tearDown(self):
        self.log.close()
        self.tmp.cleanup()

    def call(self, name, args=None, call_id=None):
        return self.episode.execute(call_id or f"call-{self.episode.request_count}", name, json.dumps(args or {}))

    def test_configuration_terra_high_and_limits(self):
        self.assertEqual(self.config.model, "gpt-5.6-terra")
        self.assertEqual(self.config.reasoning_effort, "high")
        for overrides in ({"model": "other"}, {"scientific_budget": 6},
                          {"require_full_budget": True}, {"api_ceiling_usd": "4"},
                          {"reasoning_effort": "low"}):
            with self.assertRaises(ValueError):
                replace(self.config, **overrides)

    def test_prompt_and_tools_no_private_data_or_baseline(self):
        text = json.dumps(prompts(self.config, self.episode))
        for forbidden in ("reference_q", "claim_valid", "theta", "fixed_two_check", "30/30"):
            self.assertNotIn(forbidden, text)
        self.assertEqual({t["name"] for t in tool_definitions()}, {
            "list_artifacts", "read_artifact", "recompute_peak", "refine_integration",
            "refine_sampling", "compare_runs", "budget", "submit"})
        for t in tool_definitions():
            self.assertTrue(t["strict"])
            self.assertFalse(t["parameters"]["additionalProperties"])

    def test_invalid_schema_and_unknown_evidence_uncharged(self):
        for name, args in (("reference", {}), ("read_artifact", {"id": "missing", "offset": 0, "limit": 200}),
                           ("refine_integration", {"run_id": self.instance.study["run_id"], "theta": [1, 2, 3]}),
                           ("submit", {"verdict": "ACCEPT", "diagnosis": "test",
                                       "evidence_ids": ["private"], "justification": "test"})):
            self.assertFalse(self.call(name, args)["ok"])
        self.assertEqual(self.episode.environment.spent, 0)

    def test_duplicate_and_free_retrieval(self):
        args = {"run_id": self.instance.study["run_id"]}
        first = self.call("refine_integration", args, "same")
        again = self.call("refine_integration", args, "same")
        self.assertEqual(first, again)
        self.assertEqual(self.episode.environment.spent, 3)
        key = first["result"]["run_id"]
        self.assertTrue(self.call("recompute_peak", {"run_id": key})["ok"])
        self.assertEqual(self.episode.environment.spent, 3)

    def test_actual_submit_any_spend(self):
        result = self.call("submit", {"verdict": "ABSTAIN", "diagnosis": "not enough",
                                     "evidence_ids": [], "justification": "test"})
        self.assertTrue(result["ok"])
        self.assertTrue(self.episode.evaluate()["abstained"])
        self.assertFalse(self.episode.evaluate()["correct"])
        self.assertEqual(self.episode.environment.spent, 0)

    def test_restore_purchases_without_solver(self):
        first = self.call("refine_integration", {"run_id": self.instance.study["run_id"]}, "same")
        state = json.loads(json.dumps(self.episode.checkpoint()))
        with patch("budgeted_science.claim_verification.numerics.solve", side_effect=AssertionError):
            restored = VerificationEpisode.restore(self.config, self.instance, self.log, None, state)
            repeated = restored.execute("same", "refine_integration",
                                        json.dumps({"run_id": self.instance.study["run_id"]}))
            self.assertEqual(first, repeated)
            self.assertEqual(restored.environment.spent, 3)
            result = restored.execute("retrieve", "recompute_peak", json.dumps({"run_id": first["result"]["run_id"]}))
            self.assertTrue(result["ok"])

    def test_corrupt_pending_or_identity_checkpoint_rejected(self):
        self.call("refine_integration", {"run_id": self.instance.study["run_id"]})
        for field in ("charge", "status", "study"):
            state = deepcopy(self.episode.checkpoint())
            if field == "study":
                state["study_hash"] = "wrong"
            else:
                state["environment"]["ledger"][0][field] = 0 if field == "charge" else "pending"
            with self.assertRaises(ValueError):
                VerificationEpisode.restore(self.config, self.instance, self.log, None, state)

    def test_tool_limit_stops_without_purchase(self):
        self.episode.request_count = 30
        with self.assertRaises(StopEpisode):
            self.call("budget")
        self.assertEqual(self.episode.environment.spent, 0)


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, self.instance = VerificationConfig(), VerificationInstance(examples()[0])

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def run_fake(self, gateway=None, config=None):
        return await run_episode(ROOT, self.tmp.name, mode="dry-run", config=config or self.config,
                                 instance=self.instance, gateway=gateway or VerificationGateway(),
                                 adapter=VerificationAdapter())

    async def test_complete_end_to_end_and_baseline_independence(self):
        with patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError):
            path, reason = await self.run_fake()
        self.assertEqual(reason, "submitted")
        data = json.loads((path / "evaluation.json").read_text())
        self.assertTrue(data["evaluation"]["correct"])
        self.assertEqual(data["evaluation"]["spent"], 5)
        self.assertEqual(data["fixed_policy"]["evaluation"]["spent"], 5)
        events, _ = read_events(path)
        requests = [e for e in events if e["kind"] == "api_request_sent"]
        self.assertEqual(len(requests), 3)
        body = json.loads((path / "api/generation-002-request.json").read_text())
        self.assertFalse(body["parallel_tool_calls"])
        self.assertEqual(body["reasoning"], {"effort": "high", "summary": "auto"})
        self.assertTrue(any(i.get("type") == "reasoning" for i in body["input"]))
        self.assertNotIn("reference_q", json.dumps(body))

    async def test_report_regeneration_no_tools_and_no_planning_label(self):
        path, _ = await self.run_fake()
        before = [(path / f).read_bytes() for f in ("report.md", "transcript.md")]
        with patch("budgeted_science.claim_verification.numerics.solve", side_effect=AssertionError):
            regenerate(path)
        self.assertEqual(before, [(path / f).read_bytes() for f in ("report.md", "transcript.md")])
        self.assertIn(b"Claim verification episode", before[1])

    async def test_interrupted_stream_and_resume_preserve_credits_costs_history(self):
        parent, reason = await self.run_fake(VerificationGateway(fail_turn=2))
        self.assertEqual(reason, "request_or_runner_error")
        data = json.loads((parent / "evaluation.json").read_text())
        self.assertEqual(data["evaluation"]["spent"], 3)
        self.assertTrue(data["api_budget"]["unsettled_requests"])
        previous_bytes = (parent / "events.jsonl").read_bytes()
        resume = prepare_resume(parent, mode="dry-run")
        self.assertEqual(resume["money"].status(), data["api_budget"])
        with patch.object(VerificationAdapter, "run_comparisons", side_effect=AssertionError("baseline repeated")):
            child, reason = await run_episode(ROOT, self.tmp.name, mode="dry-run",
                config=resume["config"], instance=resume["instance"], adapter=VerificationAdapter(),
                gateway=VerificationGateway(), resume=resume)
        self.assertEqual(reason, "submitted")
        result = json.loads((child / "evaluation.json").read_text())
        self.assertEqual(result["evaluation"]["spent"], 5)
        self.assertEqual(result["model_responses"], 4)
        self.assertEqual(result["api_budget"]["unsettled_requests"], data["api_budget"]["unsettled_requests"])
        self.assertEqual((parent / "events.jsonl").read_bytes(), previous_bytes)
        with self.assertRaises(ValueError):
            prepare_resume(parent, mode="dry-run")

    async def test_resume_rejects_submitted_or_mode_change(self):
        path, _ = await self.run_fake()
        for mode in ("dry-run", "live"):
            with self.assertRaises(ValueError):
                prepare_resume(path, mode=mode)

    async def test_resume_rejects_tampered_checkpoint(self):
        path, _ = await self.run_fake(VerificationGateway(fail_turn=2))
        data = json.loads((path / "checkpoint.json").read_text())
        data["payload"]["request_count"] += 1
        (path / "checkpoint.json").write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            prepare_resume(path, mode="dry-run")

    async def test_ceiling_and_response_limit_not_auto_extended(self):
        path, reason = await self.run_fake(config=replace(self.config, api_ceiling_usd="0"))
        self.assertEqual(reason, "api_ceiling")
        data = json.loads((path / "evaluation.json").read_text())
        self.assertEqual(data["model_responses"], 0)
        path, reason = await self.run_fake(config=replace(self.config, max_responses=1))
        self.assertEqual(reason, "response_limit")
        with self.assertRaises(ValueError):
            prepare_resume(path, mode="dry-run")


if __name__ == "__main__":
    unittest.main()

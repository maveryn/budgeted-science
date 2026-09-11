"""Offline agent-runner contracts. No real API calls or user credentials."""

import asyncio
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.api import OpenAIGateway, count_payload, load_api_key
from budgeted_science.agents.config import PrivateInstance, RunConfig
from budgeted_science.agents.fake import ScriptedGateway
from budgeted_science.agents.planning import PlanningEpisode, prompts, run_fixed_policy, tool_definitions
from budgeted_science.agents.records import Redactor, RunLog, digest, read_events
from budgeted_science.agents.reporting import regenerate
from budgeted_science.agents.runner import StopEpisode, generation_body, replay_output_item, run_episode
from budgeted_science.agents.spending import AccountingUnavailable, ApiBudget, ApiLimit
from budgeted_science.burgers.scoring import score_planning

REPO = Path(__file__).resolve().parents[1]


class AccountingTests(unittest.TestCase):
    def test_maximum_cost_includes_reasoning_and_cache_write_bound(self):
        budget = ApiBudget()
        self.assertEqual(budget.reserve("a", 1000, 8192), Decimal("0.16884"))
        budget.settle("a", {"input_tokens": 1000, "output_tokens": 100,
                            "output_tokens_details": {"reasoning_tokens": 90}})
        self.assertEqual(budget.known_upper, Decimal("0.007"))
        self.assertEqual(budget.reserved, 0)

    def test_missing_usage_keeps_reservation(self):
        budget = ApiBudget()
        reserved = budget.reserve("a", 1000, 8192)
        with self.assertRaises(AccountingUnavailable):
            budget.settle("a", None)
        self.assertEqual(budget.reserved, reserved)

    def test_invalid_usage_keeps_reservation(self):
        for usage in ({}, {"input_tokens": True, "output_tokens": 1},
                      {"input_tokens": 1, "output_tokens": 1, "output_tokens_details": {"reasoning_tokens": 2}}):
            budget = ApiBudget()
            budget.reserve("a", 100, 100)
            with self.assertRaises(AccountingUnavailable):
                budget.settle("a", usage)
            self.assertGreater(budget.reserved, 0)

    def test_ceiling_checked_before_generation(self):
        budget = ApiBudget("0.17")
        budget.reserve("first", 1000, 8192)
        with self.assertRaisesRegex(ApiLimit, "api_ceiling"):
            budget.reserve("second", 1, 8192)

    def test_context_limit(self):
        with self.assertRaisesRegex(ApiLimit, "input_context_limit"):
            ApiBudget().reserve("a", 256001, 8192)

    def test_counter_disagreement_is_not_hidden(self):
        budget = ApiBudget()
        budget.reserve("a", 10, 100)
        with self.assertRaisesRegex(AccountingUnavailable, "usage_exceeded_reservation"):
            budget.settle("a", {"input_tokens": 11, "output_tokens": 50})
        self.assertEqual(budget.measured[0]["usage"]["input_tokens"], 11)

    def test_cached_tokens_reduce_only_lower_estimate(self):
        budget = ApiBudget()
        budget.reserve("a", 100, 100)
        budget.settle("a", {"input_tokens": 100, "output_tokens": 10, "input_tokens_details": {"cached_tokens": 100}})
        self.assertEqual(budget.known_upper, Decimal("0.0007"))
        self.assertEqual(Decimal(budget.measured[0]["standard_cost_lower_usd"]), Decimal("0.00024"))

    def test_configuration_locks_model_effort_and_limits(self):
        for values in ({"model": "other"}, {"reasoning_effort": "low"}, {"api_ceiling_usd": "2.01"},
                       {"max_responses": 31}, {"max_output_tokens": 32769}, {"deadline_seconds": 1201}):
            with self.assertRaises(ValueError):
                RunConfig(**values)

    def test_returned_items_are_canonicalized_for_replay(self):
        reasoning = {"type": "reasoning", "id": "r1", "summary": [], "content": None,
                     "encrypted_content": "opaque", "status": None}
        function = {"type": "function_call", "id": "f1", "call_id": "c1", "name": "budget",
                    "arguments": "{}", "caller": None, "namespace": None, "status": "completed"}
        message = {"type": "message", "id": "m1", "role": "assistant", "status": "completed",
                   "phase": "commentary", "content": [{"type": "output_text", "text": "hello"}]}
        self.assertEqual(replay_output_item(reasoning),
                         {"type": "reasoning", "id": "r1", "summary": [], "encrypted_content": "opaque"})
        self.assertEqual(replay_output_item(function),
                         {"type": "function_call", "call_id": "c1", "name": "budget", "arguments": "{}", "id": "f1"})
        self.assertEqual(replay_output_item(message),
                         {"type": "message", "role": "assistant", "content": message["content"], "phase": "commentary"})
        with self.assertRaisesRegex(StopEpisode, "unsupported_output_item"):
            replay_output_item({"type": "unknown"})


class RecordTests(unittest.TestCase):
    def test_redaction_and_auth_errors(self):
        secret = "sk-synthetic-test-key-NOT-A-CREDENTIAL"
        redactor = Redactor([secret, "arbitrary-private-value"])
        cleaned = redactor.clean({"api_key": secret, "text": secret + " Bearer abc.def arbitrary-private-value"})
        self.assertNotIn(secret, json.dumps(cleaned))
        self.assertNotIn("abc.def", json.dumps(cleaned))
        error = RuntimeError("partial key fragment")
        error.status_code = 401
        self.assertNotIn("fragment", json.dumps(redactor.error(error)))
        opaque = {"encrypted_content": "opaque-sk-coincidental-ciphertext"}
        self.assertEqual(redactor.clean(opaque), opaque)

    def test_unique_runs_durable_events_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = RunLog(tmp, "test"), RunLog(tmp, "test")
            self.assertNotEqual(first.path, second.path)
            first.event("sample", text="visible before close")
            self.assertEqual(read_events(first.path)[0][0]["kind"], "sample")
            first.write_json("x.json", {})
            with self.assertRaises(FileExistsError):
                first.write_json("x.json", {})
            with self.assertRaises(ValueError):
                first.write_json("../escape.json", {})
            first.close()
            second.close()

    def test_torn_tail_not_middle_is_recoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = RunLog(tmp, "test")
            log.event("good")
            log.close()
            with (log.path / "events.jsonl").open("ab") as stream:
                stream.write(b'{"text":"\xe2\x82')
            events, torn = read_events(log.path)
            self.assertTrue(torn)
            self.assertEqual(len(events), 1)
            with (log.path / "events.jsonl").open("ab") as stream:
                stream.write(b'\n{"sequence":2}\n')
            with self.assertRaises(ValueError):
                read_events(log.path)

    def test_serialization_failure_does_not_skip_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = RunLog(tmp, "test")
            with self.assertRaises(ValueError):
                log.event("bad", value=float("nan"))
            log.event("good")
            log.close()
            self.assertEqual(read_events(log.path)[0][0]["sequence"], 1)

    def test_key_file_formats_and_multiple_key_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.txt"
            for content in ("sk-synthetic-one", 'OPENAI_API_KEY="sk-synthetic-one"'):
                path.write_text(content)
                self.assertEqual(load_api_key(path), "sk-synthetic-one")
            for content in ("", "sk-synthetic-one\nsk-synthetic-two", "sk-synthetic-one\nsk-synthetic-one"):
                path.write_text(content)
                with self.assertRaises(ValueError) as caught:
                    load_api_key(path)
                self.assertNotIn("sk-synthetic", str(caught.exception))

    def test_durable_logs_redact_synthetic_credentials(self):
        secret = "private-synthetic-value"
        with tempfile.TemporaryDirectory() as tmp:
            log = RunLog(tmp, "test", redactor=Redactor([secret]))
            log.event("run_error", error=log.redactor.error(RuntimeError(secret)))
            log.write_json("response.json", {"text": secret, "authorization": "Bearer unknown"})
            log.close()
            for path in log.path.iterdir():
                text = path.read_text()
                self.assertNotIn(secret, text)
                self.assertNotIn("Bearer unknown", text)


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = RunLog(self.tmp.name, "test")
        self.episode = PlanningEpisode(RunConfig(), PrivateInstance(), self.log)

    def tearDown(self):
        self.log.close()
        self.tmp.cleanup()

    def call(self, name, args, call_id=None):
        return self.episode.execute(call_id or f"call-{len(self.episode.executed)}", name, json.dumps(args))

    def test_private_instance_absent_from_prompts(self):
        text = json.dumps(prompts(RunConfig()))
        self.assertNotIn("0.23", text)
        self.assertNotIn("seed", text.lower())
        self.assertNotIn("fixed policy", text.lower())
        self.assertEqual(len(tool_definitions()), 7)

    def test_duplicate_observation_is_free_but_distinct_call_is_new_trial(self):
        first = self.call("observe", {"sensor_id": 2, "replicates": 1}, "same")
        again = self.call("observe", {"sensor_id": 2, "replicates": 1}, "same")
        second = self.call("observe", {"sensor_id": 2, "replicates": 1})
        self.assertEqual(first["result"], again["result"])
        self.assertTrue(again["replayed_call"])
        self.assertEqual(second["budget_after"]["spent"]["observation"], 4)
        self.assertNotEqual(first["result"], second["result"])

    def test_duplicate_id_conflict_is_not_executed(self):
        self.call("observe", {"sensor_id": 2, "replicates": 1}, "same")
        result = self.call("observe", {"sensor_id": 1, "replicates": 1}, "same")
        self.assertEqual(result["error"], "call_id_conflict")
        self.assertEqual(result["budget_after"]["spent"]["observation"], 2)

    def test_retrieval_and_submission_after_scientific_exhaustion(self):
        records = self.call("observe", {"sensor_id": 2, "replicates": 10})["result"]
        self.assertFalse(self.call("observe", {"sensor_id": 2, "replicates": 1})["ok"])
        record = self.call("record", {"record_id": records[0]["record_id"]})
        self.assertTrue(record["ok"])
        self.assertTrue(self.call("submit", {"profile": [0.0] * 16})["ok"])

    def test_forecast_compact_output_matches_full_artifact(self):
        result = self.call("simulate", {"viscosity": .2, "resolution": 32, "protocol": "forecast"})["result"]
        self.assertNotIn("fields", result)
        full = self.call("simulation_record", {"result_id": result["result_id"]})["result"]
        np.testing.assert_array_equal(result["forecast_profile"], np.asarray(full["fields"])[-1, np.arange(1, 32, 2)])
        artifact = json.loads((self.log.path / "numerical/agent/sim-00001.json").read_text())
        self.assertEqual(full, artifact)

    def test_calibration_compact_output_matches_full(self):
        result = self.call("simulate", {"viscosity": .2, "resolution": 32, "protocol": "calibration"})["result"]
        full = self.episode.simulations.results[result["result_id"]]
        np.testing.assert_array_equal(result["calibration_predictions"], np.asarray(full["fields"])[1:, [4, 8, 12]].T)

    def test_fit_logs_all_underlying_simulations(self):
        records = self.call("observe", {"sensor_id": 2, "replicates": 1})["result"]
        result = self.call("fit", {"record_ids": [records[0]["record_id"]], "resolution": 32, "max_evaluations": 16})
        self.assertTrue(result["ok"])
        events = read_events(self.log.path)[0]
        sims = [e for e in events if e["kind"] == "simulation_finished"]
        self.assertGreater(len(sims), 2)
        self.assertTrue(all(e["parent_call"] == "call-1" for e in sims))
        self.assertNotIn("fields", json.dumps(result))

    def test_repeated_simulation_logs_free_cache_reuse(self):
        args = {"viscosity": .2, "resolution": 32, "protocol": "calibration"}
        self.call("simulate", args)
        result = self.call("simulate", args)["result"]
        self.assertEqual(result["charged_credits"], 0)
        events = read_events(self.log.path)[0]
        self.assertTrue([e for e in events if e["kind"] == "simulation_finished"][-1]["reused_purchased_result"])

    def test_interrupted_work_logged_and_charged(self):
        self.episode = PlanningEpisode(RunConfig(scientific_credits=.01), PrivateInstance(), self.log)
        result = self.call("simulate", {"viscosity": .2, "resolution": 128, "protocol": "forecast"})["result"]
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertGreater(result["charged_credits"], 0)
        self.assertNotIn("forecast_profile", result)

    def test_malformed_nonfinite_arguments_uncharged(self):
        for raw in ('{"profile":[NaN]}', '{"profile":[1e999]}', '{"extra":1}', '{bad'):
            result = self.episode.execute(f"invalid-{raw}", "submit", raw)
            self.assertFalse(result["ok"])
        self.assertFalse(self.episode.execute([], "budget", "{}")["ok"])
        self.assertEqual(sum(self.episode.ledger.status()["spent"].values()), 0)

    def test_score_uses_submitted_profile(self):
        self.call("submit", {"profile": [0.0] * 16})
        evaluation = self.episode.evaluate()
        self.assertEqual(evaluation["score"], score_planning([0.0] * 16, .23))
        self.assertGreater(evaluation["score"]["normalized_profile_rmse"], .1)

    def test_fixed_policy_independent_but_paired(self):
        baseline = run_fixed_policy(RunConfig(), PrivateInstance(), self.log)
        self.assertEqual(sum(self.episode.ledger.status()["spent"].values()), 0)
        first = self.call("observe", {"sensor_id": 2, "replicates": 1})["result"][0]
        fixed = json.loads(next((self.log.path / "observations/fixed_policy").glob("*.json")).read_text())
        self.assertEqual(json.loads(json.dumps(first)), fixed)
        self.assertAlmostEqual(baseline["score"]["normalized_profile_rmse"], .03445358598907355)


class ModifiedGateway(ScriptedGateway):
    def __init__(self, modification):
        super().__init__()
        self.modification = modification

    async def stream(self, body, metadata):
        async for event in super().stream(body, metadata):
            if event["type"] == "response.completed":
                event = deepcopy(event)
                self.modification(event)
            yield event


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def run_it(self, gateway=None, **kwargs):
        return await run_episode(REPO, self.tmp.name, mode="dry-run", gateway=gateway, **kwargs)

    async def test_complete_history_requests_logs_and_offline_regeneration(self):
        gateway = ScriptedGateway()
        with patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("no key reads")):
            path, status = await self.run_it(gateway)
        self.assertEqual(status, "submitted")
        self.assertEqual(len(gateway.requests), 4)
        events = read_events(path)[0]
        responses = [e["response"] for e in events if e["kind"] == "api_response"]
        for i in range(1, 4):
            for item in responses[i-1]["output"]:
                self.assertIn(replay_output_item(item), gateway.requests[i]["input"])
            self.assertFalse(any("status" in item for item in gateway.requests[i]["input"]
                                 if item.get("type") in ("reasoning", "function_call", "message")))
        for request in gateway.requests:
            self.assertEqual(request["reasoning"], {"effort": "high", "summary": "auto"})
            self.assertFalse(request["store"])
            self.assertFalse(request["parallel_tool_calls"])
        self.assertEqual(len(list((path / "api").glob("*-request.json"))), 8)
        self.assertEqual(len(list((path / "api").glob("generation-???-response.json"))), 4)
        original = (path / "transcript.md").read_bytes()
        log_bytes = (path / "events.jsonl").read_bytes()
        with patch("budgeted_science.agents.runner.OpenAIGateway", side_effect=AssertionError("no network")):
            regenerate(path)
        self.assertEqual(original, (path / "transcript.md").read_bytes())
        self.assertEqual(log_bytes, (path / "events.jsonl").read_bytes())
        transcript = original.decode()
        self.assertIn("Returned reasoning summary", transcript)
        self.assertIn("saved locally; not sent", transcript)
        manifest = json.loads((path / "manifest.json").read_text())
        self.assertEqual(manifest["prompt_hash"], digest(prompts(RunConfig())))
        self.assertEqual(manifest["PRIVATE_harness_instance_not_agent_input"]["target_viscosity"], .23)

    async def test_stream_failure_preserves_partial_and_full_reservation(self):
        class Broken(ScriptedGateway):
            async def stream(self, body, metadata):
                self.requests.append(body)
                yield {"type": "response.output_text.delta", "delta": "partial text"}
                raise ConnectionError("interrupted network")
        gateway = Broken()
        path, status = await self.run_it(gateway)
        self.assertEqual(status, "request_or_runner_error")
        self.assertEqual(len(gateway.requests), 1)
        evaluation = json.loads((path / "evaluation.json").read_text())
        self.assertGreater(Decimal(evaluation["api_budget"]["uncertain_reserved_usd"]), 0)
        self.assertIsNone(evaluation["evaluation"]["score"])
        self.assertIn("partial text", (path / "transcript.md").read_text())

    async def test_missing_usage_stops_before_tool_execution(self):
        gateway = ModifiedGateway(lambda e: e["response"].update(usage=None))
        path, status = await self.run_it(gateway)
        self.assertEqual(status, "missing_or_invalid_usage")
        self.assertEqual(len(gateway.requests), 1)
        self.assertFalse(any(e["kind"] == "tool_requested" and e["role"] == "agent" for e in read_events(path)[0]))

    async def test_truncated_output_is_incomplete(self):
        def modify(event):
            event["type"] = "response.incomplete"
            event["response"].update(status="incomplete", incomplete_details={"reason": "max_output_tokens"})
        path, status = await self.run_it(ModifiedGateway(modify))
        self.assertEqual(status, "model_output_incomplete")
        self.assertIn("max_output_tokens", (path / "events.jsonl").read_text())

    async def test_refusal_is_incomplete(self):
        def modify(event):
            event["response"]["output"] = [{"type": "message", "content": [{"type": "refusal", "refusal": "Declined."}]}]
        _, status = await self.run_it(ModifiedGateway(modify))
        self.assertEqual(status, "refusal")

    async def test_no_submission_is_not_fabricated(self):
        _, status = await self.run_it(ModifiedGateway(lambda e: e["response"].update(output=[])))
        self.assertEqual(status, "no_submission")

    async def test_response_limit(self):
        _, status = await self.run_it(config=RunConfig(max_responses=1))
        self.assertEqual(status, "response_limit")

    async def test_offline_runner_works_without_optional_sdk(self):
        with patch.dict(sys.modules, {"openai": None}):
            _, status = await self.run_it()
        self.assertEqual(status, "submitted")

    async def test_ceiling_prevents_first_request(self):
        gateway = ScriptedGateway()
        _, status = await self.run_it(gateway, config=RunConfig(api_ceiling_usd="0.01"))
        self.assertEqual(status, "api_ceiling")
        self.assertEqual(gateway.requests, [])

    async def test_token_count_failure_is_closed(self):
        class BrokenCount(ScriptedGateway):
            async def count(self, body, metadata):
                raise RuntimeError("endpoint unavailable")
        gateway = BrokenCount()
        _, status = await self.run_it(gateway)
        self.assertEqual(status, "token_count_unavailable")
        self.assertEqual(gateway.requests, [])

    async def test_deadline(self):
        class Slow(ScriptedGateway):
            async def count(self, body, metadata):
                await asyncio.sleep(10)
        _, status = await self.run_it(Slow(), config=RunConfig(deadline_seconds=.5))
        self.assertEqual(status, "deadline")

    async def test_cancelled_stream_is_finalized_as_interrupted(self):
        class Cancelled(ScriptedGateway):
            async def stream(self, body, metadata):
                yield {"type": "response.output_text.delta", "delta": "partial"}
                raise asyncio.CancelledError()
        path, status = await self.run_it(Cancelled())
        self.assertEqual(status, "interrupted")
        self.assertTrue((path / "report.md").is_file())

    async def test_stop_at_first_valid_submission(self):
        def modify(event):
            event["response"]["output"] = [
                {"type": "function_call", "call_id": "submit", "name": "submit", "arguments": json.dumps({"profile": [0.] * 16})},
                {"type": "function_call", "call_id": "never", "name": "observe", "arguments": '{"sensor_id":2,"replicates":1}'}]
        path, status = await self.run_it(ModifiedGateway(modify))
        self.assertEqual(status, "submitted")
        data = json.loads((path / "evaluation.json").read_text())
        self.assertEqual(sum(data["evaluation"]["scientific_budget"]["spent"].values()), 0)
        self.assertEqual(data["model_responses"], 1)

    async def test_unfinalized_log_regeneration(self):
        log = RunLog(self.tmp.name, "test")
        log.write_json("manifest.json", {"mode": "dry-run", "public_configuration": RunConfig().public()})
        log.event("api_budget", budget={"uncertain_reserved_usd": ".2"})
        log.close()
        regenerate(log.path)
        self.assertIn("interrupted_without_finalization", (log.path / "report.md").read_text())


class OptionalSDKTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_sdk_serialization_with_mock_transport(self):
        try:
            import httpx
            import openai
        except ImportError:
            self.skipTest("optional agents dependency is absent")
        if tuple(int(part) for part in openai.__version__.split(".")[:2]) < (2, 54):
            self.skipTest("install the optional agents dependency for the tested SDK interface")
        captured = []
        def handler(request):
            captured.append((str(request.url), json.loads(request.content)))
            if request.url.path.endswith("input_tokens"):
                return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 123},
                                      headers={"x-request-id": "mock-count"})
            event = {"type": "response.completed", "sequence_number": 1, "response": {
                "id": "mock-response", "object": "response", "status": "completed", "model": "gpt-5.6-sol",
                "output": [], "usage": {"input_tokens": 123, "output_tokens": 0, "total_tokens": 123}}}
            return httpx.Response(200, text="data: " + json.dumps(event) + "\n\ndata: [DONE]\n\n",
                                  headers={"content-type": "text/event-stream", "x-request-id": "mock-stream"})
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gateway = OpenAIGateway("sk-synthetic-not-a-real-key", http_client=http)
        body = generation_body(RunConfig(), prompts(RunConfig()), tool_definitions())
        received_metadata = []
        try:
            counted = await gateway.count(count_payload(body), received_metadata.append)
            self.assertEqual(counted["input_tokens"], 123)
            events = [e async for e in gateway.stream(body, received_metadata.append)]
            self.assertEqual(events[0]["response"]["id"], "mock-response")
            self.assertEqual(captured[0][1], count_payload(body))
            self.assertEqual(captured[1][1], body)
            self.assertEqual(gateway.client.max_retries, 0)
            self.assertEqual(received_metadata, [{"request_id": "mock-count"}, {"request_id": "mock-stream"}])
        finally:
            await gateway.close()


if __name__ == "__main__":
    unittest.main()

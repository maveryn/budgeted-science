"""Offline tests: no real credentials, paid calls, or execution of generated code."""
import asyncio
from copy import deepcopy
from decimal import Decimal
from functools import lru_cache
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.claim_verification.numerics import configuration, solve, reference, Backend
from budgeted_science.claim_verification.studies import make_study
from budgeted_science.claim_verification.raw_analysis import RawEpisode, public_run, fixed_raw_audit
from budgeted_science.agents import verification_python as agent
from budgeted_science.agents.hosted_python import (HostedBudget, HostedGateway, FakeHostedGateway,
    REQUEST_RESERVE, CONTAINER_RESERVE, replay_hosted, MAX_BILLED_INPUT, hosted_activity)
from budgeted_science.agents.records import RunLog, digest, read_events
from budgeted_science.agents.runner import StopEpisode
from budgeted_science.agents.spending import ApiLimit, AccountingUnavailable


@lru_cache()
def fixture():
    theta = (1., .08, 1.4)
    return make_study(7102, theta, "consequential_integration",
                      solve(theta, configuration("Euler", dt=.16)), reference(theta), 0)


def args(study, **changes):
    return {"source_run_id": study["run_id"], "method": "DOP853", "dt": .01,
            "rtol": 1e-10, "atol": 1e-12, "output_spacing": .0025, "output_phase": 0, **changes}


class RawServiceTests(unittest.TestCase):
    def setUp(self):
        self.study = deepcopy(fixture())
        self.env = RawEpisode(self.study)

    def test_public_allowlist_and_no_helper_tools(self):
        public = agent.public_study(self.study)
        self.assertEqual(set(public), {"report", "original_run"})
        self.assertEqual(set(public["original_run"]), {"run_id", "status", "config", "columns", "times", "values"})
        for text in ("theta", "private", "reference_q", "claim_valid", "internal", "consequential_integration"):
            self.assertNotIn(text, json.dumps(public))
        self.assertEqual({t["name"] for t in agent.tools()}, {"simulate", "run_record", "budget", "submit"})
        for name in ("refine_integration", "recompute_peak", "refine_sampling", "compare_runs"):
            self.assertEqual(self.env.tools.call(name, {})["status"], "invalid")

    def test_combined_changes_cost_five_and_return_no_analysis(self):
        result = self.env.tools.call("simulate", args(self.study))
        self.assertEqual((result["status"], result["charge"], self.env.remaining), ("success", 5, 0))
        self.assertNotIn("q", result)
        self.assertNotIn("peak", result)
        self.assertEqual(len(result["run"]["times"]), 3201)

    def test_chained_changes_and_retrieval(self):
        first = self.env.tools.call("simulate", args(self.study, output_spacing=0))
        second = self.env.tools.call("simulate", args(self.study, source_run_id=first["run_id"]))
        self.assertEqual((first["charge"], second["charge"]), (3, 2))
        retrieved = self.env.tools.call("run_record", {"run_id": second["run_id"]})
        self.assertEqual(retrieved["run"], second["run"])
        self.assertEqual(self.env.spent, 5)

    def test_identical_config_reuses_despite_ignored_fields(self):
        request = args(self.study)
        first = self.env.tools.call("simulate", request, "same")
        self.assertEqual(self.env.tools.call("simulate", request, "same"), first)
        again = self.env.tools.call("simulate", {**request, "dt": .02}, "different")
        self.assertEqual(again["charge"], 0)
        self.assertEqual(again["run"], first["run"])

    def test_invalid_unaffordable_and_malformed_uncharged(self):
        for changes in ({"output_spacing": .00001}, {"method": "unknown"}, {"dt": .4},
                        {"source_run_id": "not-purchased"}, {"output_spacing": 0, "output_phase": .5}):
            self.assertEqual(self.env.tools.call("simulate", args(self.study, **changes))["status"], "invalid")
        self.assertEqual(self.env.spent, 0)
        self.env.tools.call("simulate", args(self.study))
        result = self.env.tools.call("simulate", args(self.study, method="Radau"))
        self.assertEqual(result["status"], "unaffordable")
        self.assertEqual(self.env.spent, 5)

    def test_failed_results_charge_and_cache(self):
        def fail(theta, config):
            return {"status": "failed", "config": config}, False
        with patch.object(self.env.backend, "get", side_effect=fail) as backend:
            result = self.env.tools.call("simulate", args(self.study))
            again = self.env.tools.call("simulate", args(self.study))
        self.assertEqual(backend.call_count, 1)
        self.assertEqual((result["status"], result["charge"], again["charge"]), ("failed", 5, 0))

    def test_cross_episode_cache_does_not_waive_charge(self):
        backend = Backend()
        one, two = RawEpisode(self.study, backend=backend), RawEpisode(self.study, backend=backend)
        a = one.tools.call("simulate", args(self.study))
        b = two.tools.call("simulate", args(self.study))
        self.assertEqual(a["run"], b["run"])
        self.assertEqual((one.spent, two.spent), (5, 5))

    def test_cpu_uses_raw_values_and_evaluator_is_private(self):
        result = fixed_raw_audit(self.env)
        self.assertTrue(result["evaluation"]["correct"])
        self.assertEqual(result["evaluation"]["spent"], 5)
        self.assertIsNone(RawEpisode(self.study).submission)

    def test_python_episode_duplicates_and_unknown_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            log = RunLog(root, "test")
            ep = agent.PythonEpisode(self.study, log)
            call = {"call_id": "a", "name": "simulate", "arguments": json.dumps(args(self.study))}
            self.assertEqual(ep.execute(call), ep.execute(call))
            self.assertEqual(ep.environment.spent, 5)
            conflict = ep.execute({**call, "arguments": "{}"})
            self.assertEqual(conflict["status"], "invalid")
            bad = ep.execute({"call_id": "b", "name": "submit", "arguments": json.dumps({
                "verdict": "ACCEPT", "diagnosis": "test", "evidence_ids": ["hidden"], "justification": "test"})})
            self.assertEqual(bad["status"], "invalid")
            log.close()


class HostedAccountingTests(unittest.TestCase):
    def test_reserves_internal_tool_pass_and_container_inside_two_dollars(self):
        budget = HostedBudget()
        budget.start_container()
        budget.reserve("a", 1)
        self.assertEqual(budget.committed, REQUEST_RESERVE+CONTAINER_RESERVE)
        with self.assertRaises(ApiLimit):
            budget.reserve("b", 1)
        budget.settle("a", {"input_tokens": 5000, "output_tokens": 100})
        budget.reserve("b", 6000)
        self.assertLessEqual(budget.committed, 2)

    def test_unknown_usage_keeps_reservation(self):
        budget = HostedBudget()
        budget.start_container()
        budget.reserve("a", 100)
        before = budget.committed
        with self.assertRaises(AccountingUnavailable):
            budget.settle("a", None)
        self.assertEqual(budget.committed, before)

    def test_large_and_invalid_counts_stop_before_generation(self):
        for count in (256001, -1, True, "100"):
            with self.assertRaises(AccountingUnavailable):
                HostedBudget().reserve("a", count)

    def test_no_second_container_or_generation(self):
        budget = HostedBudget()
        budget.start_container()
        with self.assertRaises(ApiLimit):
            budget.start_container()
        budget.reserve("a", 100)
        with self.assertRaises(AccountingUnavailable):
            budget.reserve("a", 100)

    def test_excess_usage_is_not_clamped(self):
        budget = HostedBudget()
        budget.reserve("a", 100)
        with self.assertRaises(AccountingUnavailable):
            budget.settle("a", {"input_tokens": MAX_BILLED_INPUT+1, "output_tokens": 100})
        self.assertEqual(budget.measured[0]["usage"]["input_tokens"], MAX_BILLED_INPUT+1)

    def test_replay_nullable_code_and_opaque_reasoning(self):
        item = {"id": "ci", "type": "code_interpreter_call", "container_id": "c",
                "code": None, "outputs": None, "status": "completed", "extra": 1}
        replayed = replay_hosted(item, "c")
        self.assertIsNone(replayed["code"])
        self.assertNotIn("extra", replayed)
        with self.assertRaises(StopEpisode):
            replay_hosted(item, "other")
        reasoning = {"type": "reasoning", "id": "r", "summary": [], "encrypted_content": "opaque"}
        self.assertEqual(replay_hosted(reasoning, "c"), reasoning)


class RunnerTests(unittest.TestCase):
    def test_nonterminal_extra_item_is_replayed_not_counted_as_execution(self):
        class Limited(FakeHostedGateway):
            async def stream(self, body, metadata):
                async for event in super().stream(body, metadata):
                    if event["type"] == "response.completed" and self.index == 1:
                        event["response"]["output"].append({"type": "code_interpreter_call",
                            "id": "ci_ignored", "code": "study['report']", "container_id": self.container_id,
                            "status": "interpreting", "outputs": []})
                    yield event
        with tempfile.TemporaryDirectory() as root, self.rehearsal():
            gateway = Limited()
            path, reason = asyncio.run(agent.run(root, "dry-run", root=root, gateway=gateway))
            self.assertEqual(reason, "submitted")
            result = json.loads((path/"evaluation.json").read_text())
            self.assertEqual(result["code_calls"], 1)
            self.assertEqual(len(list((path/"code").glob("*.json"))), 2)
            self.assertTrue(any(i.get("status") == "interpreting" for i in gateway.requests[1]["input"]))
            self.assertIn("nonterminal items: 1", (path/"report.md").read_text())

    def test_two_terminal_executions_still_fail_closed(self):
        with self.assertRaises(StopEpisode):
            hosted_activity([{"type": "code_interpreter_call", "status": "completed"}]*2)

    def rehearsal(self, gateway=None):
        frozen = {"public_configuration": agent.CONFIG.public()}
        return patch.object(agent, "load_prepared", return_value=(frozen, deepcopy(fixture()),
            {"evaluation": {"verdict": "REJECT", "correct": True, "spent": 5}}))

    def test_code_only_response_continues_and_preserves_history(self):
        gateway = FakeHostedGateway()
        with tempfile.TemporaryDirectory() as root, self.rehearsal():
            path, reason = asyncio.run(agent.run(root, "dry-run", root=root, gateway=gateway))
            self.assertEqual(reason, "submitted")
            second = gateway.requests[1]
            self.assertEqual(second["max_tool_calls"], 1)
            self.assertIn("code_interpreter_call.outputs", second["include"])
            self.assertTrue(any(i.get("type") == "code_interpreter_call" for i in second["input"]))
            result = json.loads((path/"evaluation.json").read_text())
            self.assertEqual(result["code_calls"], 1)
            self.assertEqual(result["api_budget"]["actual_api_usd"], 0)
            before = (path/"transcript.md").read_bytes()
            with patch.object(RawEpisode, "_simulate", side_effect=AssertionError("offline renderer ran a solver")):
                agent.render(path)
            self.assertEqual(before, (path/"transcript.md").read_bytes())

    def test_interrupted_stream_retains_events_and_reservation(self):
        class Broken(FakeHostedGateway):
            async def stream(self, body, metadata):
                yield {"type": "response.code_interpreter_call_code.delta", "delta": "print(1)"}
                raise ConnectionError("synthetic disconnect")
        with tempfile.TemporaryDirectory() as root, self.rehearsal():
            path, reason = asyncio.run(agent.run(root, "dry-run", root=root, gateway=Broken()))
            self.assertEqual(reason, "request_or_runner_error")
            events, torn = read_events(path)
            self.assertFalse(torn)
            self.assertTrue(any(e["kind"] == "api_stream_event" for e in events))
            result = json.loads((path/"evaluation.json").read_text())
            self.assertEqual(result["api_budget"]["unsettled_requests"], ["generation-001"])
            self.assertIn("print(1)", (path/"transcript.md").read_text())

    def test_one_shot_live_gate_blocks_second_launch(self):
        with tempfile.TemporaryDirectory() as root, self.rehearsal():
            with patch.object(agent, "load_api_key", side_effect=AssertionError("fake must not load credentials")):
                first, _ = asyncio.run(agent.run(root, "live", root=root, gateway=FakeHostedGateway()))
                second, reason = asyncio.run(agent.run(root, "live", root=root, gateway=FakeHostedGateway()))
            self.assertEqual(reason, "request_or_runner_error")
            result = json.loads((second/"evaluation.json").read_text())
            self.assertEqual(result["model_responses"], 0)
            self.assertNotEqual(first, second)

    def test_missing_usage_never_retries(self):
        class Missing(FakeHostedGateway):
            async def stream(self, body, metadata):
                async for event in super().stream(body, metadata):
                    if event["type"] == "response.completed":
                        event["response"]["usage"] = None
                    yield event
        with tempfile.TemporaryDirectory() as root, self.rehearsal():
            gateway = Missing()
            path, reason = asyncio.run(agent.run(root, "dry-run", root=root, gateway=gateway))
            self.assertEqual(reason, "missing_or_invalid_usage")
            self.assertEqual(len(gateway.requests), 1)


class SDKContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_container_public_upload_download_cleanup_redacted(self):
        import httpx
        calls = []
        def handler(request):
            calls.append((request.method, request.url.path, request.content))
            base = {"id": "cf", "bytes": 3, "container_id": "cntr_test", "created_at": 0,
                    "object": "container.file", "path": "../../escape.py", "source": "assistant"}
            if request.method == "POST" and request.url.path == "/v1/containers":
                body = json.loads(request.content)
                self.assertEqual(body["network_policy"], {"type": "disabled"})
                return httpx.Response(200, json={"id": "cntr_test", "memory_limit": "1g", "status": "running",
                                                "network_policy": {"type": "disabled"}})
            if request.method == "POST":
                return httpx.Response(200, json=base)
            if request.method == "DELETE":
                return httpx.Response(204)
            if request.url.path.endswith("/content"):
                return httpx.Response(200, content=b"abc")
            return httpx.Response(200, json={"object": "list", "data": [base], "has_more": False})
        with tempfile.TemporaryDirectory() as root:
            log = RunLog(root, "sdk-test")
            secret = "sk-synthetic-test-never-real"
            log.redactor.add(secret)
            gateway = HostedGateway(secret, log, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
            await gateway.start()
            value = agent.public_study(fixture())
            one = await gateway.upload("study.json", value)
            two = await gateway.upload("study.json", value)
            self.assertEqual(one, two)
            await gateway.finish()
            await gateway.close()
            log.close()
            self.assertEqual(sum(m == "POST" for m, _, _ in calls), 2)
            self.assertEqual(sum(m == "DELETE" for m, _, _ in calls), 1)
            self.assertFalse((Path(root)/"escape.py").exists())
            self.assertEqual(len(list((log.path/"container/files").glob("*.bin"))), 1)
            self.assertNotIn(secret, (log.path/"events.jsonl").read_text())
            upload = next(b for m, p, b in calls if m == "POST" and p.endswith("/files"))
            for private in (b'"theta"', b'"claim_valid"', b'"reference_q"', b'"internal"'):
                self.assertNotIn(private, upload)


if __name__ == "__main__":
    unittest.main()

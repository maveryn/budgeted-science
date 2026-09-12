"""Offline heat adapter tests: no credentials, network, or model-written execution."""
import asyncio
from contextlib import contextmanager
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents import heat_workflow_agent as agent
from budgeted_science.agents.hosted_python import FakeHostedGateway, REQUEST_RESERVE, CONTAINER_RESERVE
from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.agents.spending import ApiLimit, AccountingUnavailable


@contextmanager
def prepared(root):
    cases = [{"id": f"study-{i}", "category": "PRIVATE_MARKER", "truth": {"verdict": "ACCEPT" if i == 0 else "REJECT"}}
             for i in range(4)]
    results = [{"study_id": c["id"], "method": method, "correct": True}
               for c in cases for method in ("refinement_only", "independent_reconstruction")]
    with patch.object(agent, "load_cpu", return_value=({"cases": cases, "results": results}, "cpu-hash")), \
         patch.object(agent, "bundle", return_value={"artifacts": {"report.md": "public report"}}), \
         patch.object(agent, "provenance", return_value={"source_manifest_hash": "fixture"}):
        yield agent.prepare(Path(root)/"unused-cpu", root=root)


class HeatAdapterTests(unittest.TestCase):
    def test_only_submit_and_no_prescribed_solver(self):
        self.assertEqual([t["name"] for t in agent.tools()], ["submit"])
        self.assertIsNone(agent.CONFIG.scientific_budget)
        text = json.dumps(agent.prompts({"path": "study.json"}))
        for forbidden in ("premature_stopping", "spatial_extraction", "boundary_mismatch", "0.312029", "Fourier"):
            self.assertNotIn(forbidden, text)

    def test_bundle_allowlist_lossless_and_no_private_files(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            for name in ("intended.json", "run_config.json", "solver_log.json", "analysis_result.json"):
                (path/name).write_text('{"test": 1}')
            for name in ("report.md", "analysis.py"):
                (path/name).write_text("literal source")
            (path/"private.json").write_text('"PRIVATE_MARKER"')
            field = np.arange(9).reshape(3, 3)/7
            np.savez(path/"trajectory.npz", x=np.arange(3), y=np.arange(3), T=field)
            bundle = agent.bundle(path)
            self.assertEqual(len(bundle["artifacts"]), 7)
            np.testing.assert_array_equal(bundle["artifacts"]["trajectory.json"]["T"], field)
            self.assertNotIn("PRIVATE_MARKER", json.dumps(bundle))

    def test_private_truth_excluded_from_upload_and_submit_result(self):
        with tempfile.TemporaryDirectory() as root, prepared(root) as frozen:
            _, study, _ = agent.load_prepared(frozen/"cases/study-0")
            self.assertNotIn("PRIVATE_MARKER", json.dumps(agent.public_study(study)))
            log = RunLog(root, "test")
            episode = agent.PythonEpisode(study, log)
            call = {"name": "submit", "call_id": "a", "arguments": json.dumps({
                "verdict": "ACCEPT", "diagnosis": "test", "evidence_ids": ["report.md"], "justification": "test"})}
            result = episode.execute(call)
            self.assertEqual(result, {"status": "submitted"})
            self.assertEqual(episode.execute(call), result)
            self.assertEqual(episode.execute({**call, "arguments": "{}"})["status"], "invalid")
            self.assertTrue(episode.evaluate()["correct"])
            log.close()

    def test_invalid_submit_does_not_end_episode(self):
        with tempfile.TemporaryDirectory() as root:
            log = RunLog(root, "test")
            episode = agent.PythonEpisode({"private": {"truth": {"verdict": "ACCEPT"}}}, log)
            self.assertFalse(episode.evaluate()["completed"])
            for args in ('{}', '{"verdict":"YES"}', 'NaN'):
                self.assertEqual(episode.execute({"name": "submit", "call_id": args, "arguments": args})["status"], "invalid")
            self.assertIsNone(episode.submission)
            log.close()

    def test_frozen_evidence_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as root, prepared(root) as frozen:
            path = frozen/"cases/study-0"
            (path/"comparison.json").write_text("[]")
            with self.assertRaises(ValueError):
                agent.load_prepared(path)

    def test_cross_episode_spending_and_unknown_usage(self):
        money = agent.CampaignBudget("0.95", live=True)
        money.start_container()
        with self.assertRaises(ApiLimit):
            money.reserve("one", 100)
        money = agent.CampaignBudget("0.5", live=True)
        money.start_container()
        money.reserve("one", 100)
        with self.assertRaises(AccountingUnavailable):
            money.settle("one", None)
        self.assertEqual(money.committed, Decimal("0.5")+CONTAINER_RESERVE+REQUEST_RESERVE)
        self.assertEqual(money.status()["prior_episode_upper_usd"], "0.5")

    def test_container_cannot_cross_total_ceiling(self):
        money = agent.CampaignBudget("1.99", live=True)
        with self.assertRaises(ApiLimit):
            money.start_container()
        self.assertFalse(money.container_attempted)

    def test_four_isolated_offline_episodes_and_report_regeneration(self):
        instances = []
        class Fake(FakeHostedGateway):
            def __init__(self):
                super().__init__()
                instances.append(self)
        with tempfile.TemporaryDirectory() as root, prepared(root) as frozen:
            with patch.object(agent.transport, "load_api_key", side_effect=AssertionError("credential access")):
                path = asyncio.run(agent.campaign(frozen, "dry-run", root=root, gateway_factory=Fake))
            result = agent.read_json(path/"summary.json")
            self.assertEqual((result["completed"], result["correct"]), (4, 0))
            self.assertEqual(len(instances), 4)
            for gateway in instances:
                self.assertEqual(len(gateway.requests), 2)
                self.assertEqual(len(gateway.requests[0]["input"]), 2)
                self.assertEqual(gateway.requests[0]["reasoning"]["effort"], "high")
                self.assertNotIn("PRIVATE_MARKER", json.dumps(gateway.requests))
            before = (path/"report.md").read_bytes()
            with patch.object(agent.transport, "run", side_effect=AssertionError("renderer must not run")):
                agent.render_campaign(path)
                for row in result["results"]:
                    agent.render(path/row["relative_path"])
            self.assertEqual(before, (path/"report.md").read_bytes())
            self.assertLess(Decimal(result["committed_upper_usd"]), 2)
            self.assertTrue(all(r["api_budget"]["actual_api_usd"] == 0 for r in result["results"]))

    def test_interrupted_stream_halts_batch_and_retains_reservation(self):
        class Broken(FakeHostedGateway):
            async def stream(self, body, metadata):
                yield {"type": "response.code_interpreter_call_code.delta", "delta": "partial code"}
                raise ConnectionError("synthetic interruption")
        with tempfile.TemporaryDirectory() as root, prepared(root) as frozen:
            path = asyncio.run(agent.campaign(frozen, "dry-run", root=root, gateway_factory=Broken))
            result = agent.read_json(path/"summary.json")
            self.assertEqual(len(result["results"]), 1)
            self.assertEqual(Decimal(result["committed_upper_usd"]), REQUEST_RESERVE+CONTAINER_RESERVE)
            self.assertEqual(result["completed"], 0)
            episode = path/result["results"][0]["relative_path"]
            self.assertIn("partial code", (episode/"transcript.md").read_text())

    def test_single_live_campaign_gate_no_repeated_attempt(self):
        with tempfile.TemporaryDirectory() as root, prepared(root) as frozen:
            with patch.object(agent.transport, "load_api_key", side_effect=AssertionError("no keys for fake")):
                asyncio.run(agent.campaign(frozen, "live", root=root, gateway_factory=FakeHostedGateway))
                with self.assertRaises(FileExistsError):
                    asyncio.run(agent.campaign(frozen, "live", root=root, gateway_factory=FakeHostedGateway))

    def test_duplicate_case_rejected_before_transport(self):
        with tempfile.TemporaryDirectory() as root, prepared(root) as frozen:
            manifest = agent.read_json(frozen/"manifest.json")
            manifest["slots"][1] = manifest["slots"][0]
            (frozen/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                asyncio.run(agent.campaign(frozen, "dry-run", root=root))


if __name__ == "__main__":
    unittest.main()

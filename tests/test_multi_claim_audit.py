"""Matched audit contracts; no real credentials or model calls."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from budgeted_science.multi_claim_audit import core as c
from budgeted_science.agents import multi_claim_audit as a
from budgeted_science.agents.records import RunLog, read_events


class MultiClaimAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = c.build_study()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log = RunLog(self.root, "test")
        self.episode = a.Episode(a.Config(), a.Instance(self.study), self.log)
        self.counter = 0

    def tearDown(self):
        self.log.close()
        self.temp.cleanup()

    def call(self, name, **kwargs):
        self.counter += 1
        return self.episode.execute(str(self.counter), name, json.dumps(kwargs))

    def verdicts(self, value="ABSTAIN"):
        return {f"C{i}": value for i in range(1, 7)}

    def test_reference_and_literal_report(self):
        trajectory = c._solve_low(c.REPORT_THETA, c.harder_config(budget=32))
        self.assertEqual(len(self.study["public"]["claims"]), 6)
        for claim in self.study["public"]["claims"]:
            value = trajectory.sample([claim["time"]])[0, ("x", "y").index(claim["variable"])]
            self.assertEqual(float(format(value, ".10g")), claim["reported_value"])
            self.assertIn(claim["text"], self.study["public"]["report"])
        for ref in self.study["private"]["references"].values():
            self.assertLess(ref["max_solver_disagreement"], 1e-7)
            self.assertLess(ref["max_service_disagreement"], 1e-6)

    def test_same_target_and_noise_as_planning(self):
        bounds = np.asarray(c.harder_config(budget=32).ranges)
        target = np.random.default_rng(6000).uniform(bounds[:, 0], bounds[:, 1])
        np.testing.assert_array_equal(target, self.study["private"]["target_parameters"])
        other = c.PlanningEnvironment(target, c.harder_config(budget=32), noise_seed=60000)
        for var, time in (("x", 4.), ("y", 6.)):
            self.assertEqual(self.call("measure_target", variable=var, time=time)["value"],
                             other.tools.measure_target(var, time)["value"])

    def test_prices_original_and_cache(self):
        original = self.call("simulate_low", theta=list(c.REPORT_THETA))
        self.assertEqual((original["result_id"], original["charge"]), ("original", 0))
        self.assertEqual(self.call("simulate_low", theta=[1.01, .08, 1.4])["charge"], 1)
        first = self.call("simulate_high", theta=list(c.REPORT_THETA))
        repeat = self.call("simulate_high", theta=list(c.REPORT_THETA))
        self.assertEqual(first["values"], repeat["values"])
        self.assertEqual((first["charge"], repeat["charge"]), (8, 0))
        self.assertEqual(self.episode.environment.status()["spent"], 9)

    def test_noisy_measurement_retrieval_not_replication(self):
        self.assertEqual(self.call("measure_target", variable="x", time=1)["charge"], 0)
        first = self.call("measure_target", variable="x", time=4)
        second = self.call("measure_target", variable="x", time=4)
        self.assertEqual(first["value"], second["value"])
        self.assertEqual((first["noise_std"], first["charge"], second["charge"]), (.1, 12, 0))

    def test_invalid_actions_free(self):
        for name, args in [("measure_target", {"variable": "x", "time": 1.1}),
                           ("simulate_low", {"theta": [float("nan"), .08, 1.4]}),
                           ("simulate_high", {"theta": [1., .08]}),
                           ("simulate_high", {"theta": [3., .08, 1.4]}),
                           ("simulate_high", {"theta": [1., .08, 1.4], "target": True}),
                           ("private_reference", {})]:
            self.assertEqual(self.call(name, **args)["status"], "invalid")
        self.assertEqual(self.episode.environment.status()["spent"], 0)

    def test_independent_ledgers(self):
        self.call("simulate_high", theta=list(c.REPORT_THETA))
        other = c.Audit(self.study)
        self.assertEqual(other.dispatch("simulate_high", {"theta": list(c.REPORT_THETA)})["charge"], 8)

    def test_duplicate_call_does_not_purchase(self):
        args = json.dumps({"variable": "x", "time": 4.})
        one = self.episode.execute("duplicate", "measure_target", args)
        two = self.episode.execute("duplicate", "measure_target", args)
        self.assertEqual(one, two)
        conflict = self.episode.execute("duplicate", "measure_target", json.dumps({"variable": "y", "time": 4.}))
        self.assertEqual(conflict["status"], "invalid")
        self.assertEqual(self.episode.environment.status()["spent"], 12)

    def test_failed_solve_charged_and_cached(self):
        with patch("budgeted_science.resource_planning.environment._solve_low", side_effect=ValueError("failure")) as solver:
            first = self.call("simulate_low", theta=[1.01, .08, 1.4])
            repeat = self.call("simulate_low", theta=[1.01, .08, 1.4])
        self.assertEqual((first["status"], first["charge"], repeat["charge"]), ("failed", 1, 0))
        self.assertEqual(solver.call_count, 1)

    def test_fixed_control_32_credits(self):
        c.fixed_policy(self.call, deepcopy(self.study["public"]))
        result = self.episode.evaluate()
        self.assertTrue(result["completed"])
        self.assertEqual((result["correct"], result["scientific_status"]["spent"]), (6, 32))
        self.assertEqual([r["kind"] for r in result["scientific_status"]["ledger"]],
                         ["simulate_high", "measure_target", "measure_target"])

    def test_free_submission_after_exhaustion(self):
        for var in ("x", "y"):
            self.call("measure_target", variable=var, time=4)
        self.call("simulate_high", theta=list(c.REPORT_THETA))
        with patch("budgeted_science.resource_planning.environment._solve_low", side_effect=AssertionError("must not execute")):
            self.assertEqual(self.call("simulate_low", theta=[1.01, .08, 1.4])["status"], "unaffordable")
        self.assertEqual(self.call("evidence")["status"], "success")
        self.assertEqual(self.call("submit", verdicts=self.verdicts(), evidence_ids=[], explanation="unresolved")["status"], "submitted")
        self.assertEqual(self.episode.evaluate()["abstained"], 6)

    def test_public_privacy(self):
        material = json.dumps([a.prompts(a.Config(), self.episode), a.tool_definitions(), self.call("evidence"),
                               self.call("get_status"), self.call("compare_cached_candidates")])
        for secret in ("target_parameters", "target_seed", "noise_seed", "radau_values", "reference_value"):
            self.assertNotIn(secret, material)
        for value in self.study["private"]["target_parameters"]:
            self.assertNotIn(str(value), material)

    def test_free_comparison_does_not_solve(self):
        self.call("simulate_high", theta=list(c.REPORT_THETA))
        with patch("budgeted_science.resource_planning.environment._solve_high", side_effect=AssertionError("unpaid solver")), \
             patch("budgeted_science.resource_planning.environment._solve_low", side_effect=AssertionError("unpaid solver")):
            self.assertEqual(self.call("compare_cached_candidates")["status"], "success")
            self.call("evidence")
            self.call("get_status")

    def test_scoring_boundaries_abstention_and_wrong(self):
        self.assertEqual(c.classify(105, 100)["verdict"], "ACCEPT")
        self.assertEqual(c.classify(105.001, 100)["verdict"], "REJECT")
        self.assertEqual(self.episode.evaluate()["incomplete_claims"], 6)
        verdicts = {k: v["verdict"] for k, v in self.study["private"]["truth"].items()}
        verdicts["C1"], verdicts["C2"] = "REJECT", "ABSTAIN"
        self.call("submit", verdicts=verdicts, evidence_ids=["original"], explanation="Fixture")
        r = self.episode.evaluate()
        self.assertEqual((r["correct"], r["wrong"], r["abstained"], r["false_rejections"]), (4,1,1,1))
        self.assertEqual(self.call("measure_target", variable="x", time=4)["status"], "invalid")

    def test_submission_schema(self):
        self.assertEqual(self.call("submit", verdicts={"C1": "ACCEPT"}, evidence_ids=[], explanation="x")["status"], "invalid")
        self.assertEqual(self.call("submit", verdicts=self.verdicts(), evidence_ids=["unbought"], explanation="x")["status"], "invalid")
        self.assertIsNone(self.episode.submission)

    def test_complete_numerical_artifact(self):
        result = self.call("simulate_high", theta=list(c.REPORT_THETA))
        events, torn = read_events(self.log.path)
        self.assertFalse(torn)
        event = next(e for e in events if e["kind"] == "simulation_finished")
        artifact = a.read_json(self.log.path/event["artifact"])
        self.assertEqual(artifact["interpolation"], "dop853_dense")
        saved = next(e["output"] for e in events if e["kind"] == "tool_result" and e["name"] == "simulate_high")
        self.assertEqual(saved["values"], result["values"])

    def test_frozen_limits(self):
        for kwargs in ({"api_ceiling_usd": "2"}, {"model": "gpt-5.6-sol"}, {"reasoning_effort": "low"}, {"scientific_budget": 40}):
            with self.assertRaises(ValueError):
                a.Config(**kwargs)

    def test_full_offline_rehearsal(self):
        with patch.object(a, "build_study", return_value=deepcopy(self.study)):
            prepared = a.prepare(self.root)
        with patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("no keys")):
            path = asyncio.run(a.run(prepared, "dry-run", self.root))
        result = a.read_json(path/"evaluation.json")
        self.assertEqual(result["termination_reason"], "submitted")
        self.assertEqual((result["evaluation"]["scientific_status"]["spent"], result["evaluation"]["abstained"]), (32,6))
        self.assertEqual(result["fixed_policy"]["correct"], 6)
        before = (path/"transcript.md").read_text()
        with patch.object(c, "_solve_high", side_effect=AssertionError("offline")), patch.object(c, "_solve_low", side_effect=AssertionError("offline")):
            a.regenerate(path)
        self.assertEqual(before, (path/"transcript.md").read_text())
        body = a.read_json(path/"api/generation-002-request.json")
        self.assertTrue(any(i.get("type") == "reasoning" for i in body["input"]))
        self.assertEqual(body["reasoning"]["effort"], "high")

    def test_no_second_live_launch_or_tampered_inputs(self):
        with patch.object(a, "build_study", return_value=deepcopy(self.study)):
            prepared = a.prepare(self.root)
        # Injected fake exercises live launch guard, never credentials/network.
        asyncio.run(a.run(prepared, "live", self.root, gateway=a.Fake()))
        with self.assertRaises(FileExistsError):
            asyncio.run(a.run(prepared, "live", self.root, gateway=a.Fake()))
        data = a.read_json(prepared/"manifest.json")
        data["payload_hash"] = "tampered"
        (prepared/"manifest.json").write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            a.load_prepared(prepared)


if __name__ == "__main__":
    unittest.main()

"""Small CPU transport demo: numerical, isolation, accounting and reporting contracts."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.transport_verification import numerics as n
from budgeted_science.transport_verification.environment import Backend, Episode, within
from budgeted_science.transport_verification import experiment as ex


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.studies, cls.commissioning = ex.build_catalog()
        cls.study = cls.studies[0]
        cls.cfg = n.config(64, 1/256, "centered", "RK2", 1/128)

    def test_initial_condition_and_periodicity(self):
        p = n.SYSTEMS[0]
        xs = np.linspace(0, 1, 40)
        np.testing.assert_allclose(n.exact_images(p, xs, 0), n.exact_images(p, xs+1, 0), atol=1e-14)
        self.assertAlmostEqual(float(n.exact_images(p, n.X0, 0)), 1.)

    def test_reference_agreement_and_modes(self):
        for s in self.studies[::4]:
            ref = s["reference"]
            self.assertLess(ref["checks"]["image_fourier_max_abs"], 1e-10)
            self.assertLess(max(ref["checks"]["qoi_max_abs_differences"].values()), 1e-7)
            self.assertTrue(0 < ref["qois"]["crossing"] < ref["qois"]["arrival"] < n.T)

    def test_candidate_convergence(self):
        for p in n.SYSTEMS:
            errors = []
            for nx in (32, 64, 128):
                cfg = n.config(nx, 1/1024, "centered", "RK2", 1/512)
                run = n.solve(p, cfg)
                errors.append(max(abs(np.asarray(run["sensor"])-n.exact_images(p, n.SENSOR, run["times"]))))
            self.assertGreater(errors[0], errors[1])
            self.assertGreater(errors[1], errors[2])

    def test_mass_and_complete_work(self):
        for method in ("Euler", "RK2"):
            cfg = n.config(64, 1/1024, "upwind", method, 1/257)
            run = n.solve(n.SYSTEMS[1], cfg)
            target = n.WIDTH*np.sqrt(2*np.pi)*np.exp(-.1*np.array(run["times"]))
            np.testing.assert_allclose(run["mass"], target, atol=1e-6)
            self.assertEqual(run["work"], n.quote(cfg)["work"])
            self.assertEqual(run["times"][-1], 1.)
            self.assertTrue(np.isfinite(run["fields"]).all())

    def test_sampling_uses_internal_time_interpolation(self):
        p = n.SYSTEMS[0]
        coarse = n.solve(p, n.config(32, 1/128, output_dt=1/8))
        fine = n.solve(p, n.config(32, 1/128, output_dt=1/128))
        np.testing.assert_allclose(np.array(fine["fields"])[::16], coarse["fields"])
        self.assertGreater(n.qois(fine)["peak"], n.qois(coarse)["peak"])
        self.assertEqual(coarse["rhs_evaluations"], fine["rhs_evaluations"])

    def test_qoi_extraction_and_absent_crossing(self):
        r = {"status": "complete", "times": [0., .5, 1.], "sensor": [0., .2, .1]}
        self.assertEqual(n.qois(r), {"peak": .2, "arrival": .5, "exposure": .125, "crossing": .25})
        r["sensor"] = [0., .05, .05]
        self.assertIsNone(n.qois(r)["crossing"])
        r["status"] = "failed"
        with self.assertRaises(ValueError):
            n.qois(r)

    def test_invalid_and_unstable_configuration(self):
        for kwargs in ({"nx": True}, {"nx": 33}, {"dt": 0}, {"dt": float("nan")},
                       {"dt": .13}, {"spatial_method": "magic"}, {"output_dt": -1}):
            with self.assertRaises(ValueError):
                n.config(**kwargs)
        with self.assertRaises(ValueError):
            n.validate(n.SYSTEMS[2], n.config(128, .25))

    def test_catalog_has_twelve_balanced_literal_claims(self):
        self.assertEqual(len(self.studies), 12)
        self.assertEqual(len(self.commissioning), 24)
        self.assertEqual(len({s["id"] for s in self.studies}), 12)
        self.assertEqual(sum(s["private_selection"]["desired_valid"] for s in self.studies), 6)
        for s in self.studies:
            claim = s["public"]["claim"]
            self.assertEqual(claim["value"], float(format(n.qois(s["original"])[claim["quantity"]], ".10g")))
            self.assertIn(format(claim["value"], ".10g"), s["public"]["report"])
            self.assertEqual(within(claim["value"], s["reference"]["qois"][claim["quantity"]], .03), s["private_selection"]["desired_valid"])

    def test_public_view_has_no_truth_or_generation_labels(self):
        view = Episode(self.study).tools.call("describe")
        text = json.dumps(view)
        self.assertNotIn("qoi_max_abs", text)
        self.assertNotIn("desired_valid", text)
        self.assertNotIn("private_selection", text)
        self.assertNotIn(str(self.study["reference"]["qois"]["peak"]), text)

    def test_exact_charging_and_free_reuse(self):
        env = Episode(self.study)
        one = env.tools.call("run_verification", self.cfg)
        two = env.tools.call("run_verification", self.cfg)
        self.assertEqual(one["charge"], n.quote(self.cfg)["credits"])
        self.assertEqual(two["charge"], 0)
        self.assertEqual(env.budget()["spent"], one["charge"])
        self.assertEqual(env.tools.call("run_verification", self.study["original"]["config"])["charge"], 0)

    def test_invalid_unaffordable_requests_do_not_execute(self):
        def forbidden(*args):
            raise AssertionError("unpaid solver call")
        env = Episode(self.study, .125, Backend(forbidden))
        self.assertIn("error", env.tools.call("run_verification", self.cfg))
        self.assertIn("error", env.tools.call("run_verification", {"nx": -1}))
        self.assertEqual(env.spent, 0)

    def test_warm_cold_and_cross_episode_equivalence(self):
        backend = Backend()
        a = Episode(self.study, backend=backend).tools.call("run_verification", self.cfg)
        b = Episode(self.study, backend=backend).tools.call("run_verification", self.cfg)
        c = Episode(self.study).tools.call("run_verification", self.cfg)
        self.assertFalse(a.pop("backend_cache_hit"))
        self.assertTrue(b.pop("backend_cache_hit"))
        c.pop("backend_cache_hit")
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_failure_work_is_charged_and_failure_cached(self):
        calls = []
        def fail(p, cfg):
            calls.append(cfg)
            result = n.solve(p, cfg)
            result.update(status="failed", reason="injected failure", work=128, credits=128/n.WORK_UNIT)
            return result
        backend = Backend(fail)
        for _ in range(2):
            env = Episode(self.study, backend=backend)
            response = env.tools.call("run_verification", self.cfg)
            self.assertEqual(response["status"], "failed")
            self.assertEqual(env.spent, 128)
        self.assertEqual(len(calls), 1)

    def test_uncertain_failure_retains_reservation(self):
        def fail(*a):
            raise RuntimeError("interrupted")
        env = Episode(self.study, backend=Backend(fail))
        with self.assertRaises(RuntimeError):
            env.tools.call("run_verification", self.cfg)
        self.assertEqual(env.spent, n.quote(self.cfg)["work"])
        self.assertTrue(env.evaluation()["incomplete"])

    def test_duplicate_call_id_no_purchase(self):
        env = Episode(self.study)
        a = env.tools.call("run_verification", self.cfg, "c1")
        self.assertEqual(a, env.tools.call("run_verification", self.cfg, "c1"))
        self.assertEqual(env.spent, n.quote(self.cfg)["work"])
        with self.assertRaises(ValueError):
            env.tools.call("budget", {}, "c1")

    def test_inspection_recompute_compare(self):
        env = Episode(self.study)
        check = env.tools.call("run_verification", self.cfg)
        read = env.tools.call("inspect_existing_run", {"run_id": check["run_id"], "limit": 3})
        self.assertEqual(read["next_offset"], 3)
        self.assertEqual(len(read["times"]), 3)
        self.assertEqual(read["qois"], check["qois"])
        comparison = env.tools.call("compare_runs", {"run_ids": ["original", check["run_id"]]})
        self.assertAlmostEqual(comparison["differences"][0]["peak"], check["qois"]["peak"]-n.qois(self.study["original"])["peak"])

    def test_submission_validation_abstention_and_boundary(self):
        self.assertTrue(within(1.03, 1., .03))
        self.assertFalse(within(1.03001, 1., .03))
        env = Episode(self.study)
        self.assertIn("error", env.tools.call("submit", {"verdict": "ACCEPT", "evidence_ids": ["missing"], "justification": ""}))
        env.tools.call("submit", {"verdict": "ABSTAIN", "evidence_ids": ["original"], "justification": "not enough"})
        e = env.evaluation()
        self.assertTrue(e["abstention"])
        self.assertFalse(e["correct"])
        self.assertFalse(e["incomplete"])

    def test_policy_plan_does_not_use_claim_value_or_truth(self):
        public = deepcopy(self.study["public"])
        changed = deepcopy(public)
        changed["claim"]["value"] *= 1000
        for policy in ex.POLICIES:
            with patch.object(n, "solve", side_effect=AssertionError("unpaid solve")), patch.object(n, "reference", side_effect=AssertionError("reference queried")):
                a = ex.choose_configuration(public, 4, policy)
                b = ex.choose_configuration(changed, 4, policy)
            self.assertEqual(a, b)
            self.assertNotEqual(a, public["configuration"])
            self.assertLessEqual(n.quote(a)["credits"], 4)
            n.validate(public["system"], a)

    def test_logging_and_offline_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = ex.episode(self.study, "balanced", Backend(), Path(directory))
            before = (path/"transcript.md").read_bytes()
            with patch.object(n, "solve", side_effect=AssertionError("offline solve")), patch.object(ex, "run_policy", side_effect=AssertionError("offline policy")):
                ex.render_episode(path)
            self.assertEqual(before, (path/"transcript.md").read_bytes())
            events, torn = read_events(path)
            self.assertFalse(torn)
            self.assertEqual(sum(e["kind"] == "tool_request" for e in events), 3)
            self.assertTrue(list((path/"numerical").glob("*.json")))
            result = json.loads((path/"result.json").read_text())
            self.assertFalse(result["evaluation"]["incomplete"])
            self.assertEqual(result["api_dollars"], 0)

    def test_partial_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            log = RunLog(directory, "partial")
            log.event("tool_request", name="budget", arguments={})
            log.close()
            with (log.path/"events.jsonl").open("ab") as stream:
                stream.write(b'{"sequence":2')
            ex.render_episode(log.path)
            self.assertIn("Interrupted", (log.path/"transcript.md").read_text())

    def test_hand_checked_aggregate(self):
        rows = []
        for p, correct in (("balanced", True), ("space_focused", False)):
            rows.append({"case_id": "a", "policy": p, "quantity": "peak", "evaluation": {
                "correct": correct, "incomplete": False, "coverage": True, "abstention": False,
                "verdict": "ACCEPT" if correct else "REJECT", "valid": True, "spent": 2.}})
        out = ex.aggregate(rows, ["a", "b"])
        self.assertEqual(out["best_tested_fixed_correct"], 1)
        self.assertEqual(out["hindsight_fixed_selection_correct"], 1)
        self.assertEqual(out["policies"]["balanced"]["incomplete"], 1)
        self.assertEqual(out["policies"]["space_focused"]["false_rejection"], 1)


if __name__ == "__main__":
    unittest.main()

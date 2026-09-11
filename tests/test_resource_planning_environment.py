"""Offline predator-prey environment contracts; no API calls or credentials."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from itertools import product
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from scipy.integrate import solve_ivp

from budgeted_science.resource_planning import Config, DEBUG_THETA, Episode, PublicTools
from budgeted_science.resource_planning import environment as env


def independent_rhs(time, state, theta):
    prey, predator = state
    growth, interaction, mortality = theta
    return [growth * prey - interaction * prey * predator - prey ** 2 / 100,
            9 * interaction * prey * predator / 10 - mortality * predator]


def strict_json(value):
    return json.loads(json.dumps(value, allow_nan=False))


class TestConfig(unittest.TestCase):
    def test_public_defaults_have_only_advertised_fields(self):
        config = Config()
        public = config.public()
        self.assertEqual(set(public), {"bounds", "initial", "working_times", "costs", "budget", "tolerance"})
        self.assertEqual(public["bounds"], [[.8, 1.2], [.06, .10], [1.1, 1.7]])
        self.assertEqual(config.bounds, config.ranges)
        self.assertEqual(public["initial"], [10, 5])
        self.assertEqual(public["working_times"], [index / 2 for index in range(1, 17)])
        self.assertEqual(public["costs"], {"low": 1, "high": 8, "measurement": 12})
        self.assertEqual(public["budget"], 40)
        self.assertEqual(public["tolerance"], .1)
        self.assertEqual(strict_json(public), public)

    def test_settings_and_caller_inputs_cannot_mutate_config(self):
        initial, costs = [10, 5], {"low": 1, "high": 8, "measurement": 12}
        config = Config(initial=initial, costs=costs)
        initial[0] = 99
        costs["low"] = 99
        with self.assertRaises(FrozenInstanceError):
            config.budget = 100
        with self.assertRaises(TypeError):
            config.costs["low"] = 0
        public = config.public()
        public["costs"]["low"] = 0
        public["bounds"][0][0] = -100
        self.assertEqual(config.initial, (10, 5))
        self.assertEqual(config.costs["low"], 1)
        self.assertEqual(config.ranges[0][0], .8)

    def test_bad_config_and_target_fail_before_numerical_work(self):
        cases = [{"budget": -1}, {"budget": True}, {"budget": float("inf")},
                 {"tolerance": 0}, {"tolerance": -1}, {"tolerance": 2},
                 {"ranges": []}, {"ranges": [(0, 1)] * 3},
                 {"ranges": [(1, 1)] * 3}, {"ranges": [(1, 2, 3)] * 3},
                 {"initial": [1]}, {"initial": [0, 1]}, {"initial": [True, 2]},
                 {"working_times": []}, {"working_times": [1, 1]},
                 {"working_times": [1, .5]}, {"working_times": [9]},
                 {"working_times": [float("nan")]}, {"costs": {}},
                 {"costs": {"low": 0, "high": 8, "measurement": 12}}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Config(**kwargs)
        with patch.object(env, "_solve_high") as solver:
            for theta in (None, [], [1, .08, 2], [True, .08, 1.4]):
                with self.subTest(theta=theta), self.assertRaises(ValueError):
                    Episode(theta)
            with self.assertRaises(ValueError):
                Episode(DEBUG_THETA, config={})
            with self.assertRaises(ValueError):
                Episode(DEBUG_THETA, log=object())
            solver.assert_not_called()


class TestNumerics(unittest.TestCase):
    def test_high_matches_independent_radau_at_corners_and_debug(self):
        times = np.unique(np.r_[np.linspace(0, 8, 65), .025, .37, 1.23456789, 7.999])
        for theta in [DEBUG_THETA, *product(*Config().ranges)]:
            with self.subTest(theta=theta):
                actual = env._solve_high(theta, Config()).sample(times)
                reference = solve_ivp(independent_rhs, (0, 8), [10, 5], args=(theta,),
                                      method="Radau", rtol=2e-12, atol=2e-14, dense_output=True)
                self.assertTrue(reference.success)
                self.assertLess(float(np.max(np.abs(actual - reference.sol(times).T))), 1e-6)
                np.testing.assert_array_equal(actual[0], [10, 5])

    def test_high_uses_specified_solver_and_tolerances(self):
        episode = Episode(DEBUG_THETA)
        with patch.object(env, "solve_ivp", wraps=solve_ivp) as solver:
            result = episode.tools.simulate_high(DEBUG_THETA, [.37, 8])
        self.assertEqual(result["status"], "success")
        self.assertEqual(solver.call_count, 1)
        self.assertEqual(solver.call_args.kwargs["method"], "DOP853")
        self.assertEqual(solver.call_args.kwargs["rtol"], 1e-10)
        self.assertEqual(solver.call_args.kwargs["atol"], 1e-12)
        self.assertTrue(solver.call_args.kwargs["dense_output"])

    def test_euler_step_and_linear_interpolation(self):
        episode = Episode(DEBUG_THETA)
        times = [0, .05, .1, .15, .2, 8]
        result = episode.tools.simulate_low(DEBUG_THETA, times)
        initial = np.array([10., 5.])
        first = initial + .1 * np.array(independent_rhs(0, initial, DEBUG_THETA))
        second = first + .1 * np.array(independent_rhs(.1, first, DEBUG_THETA))
        expected = [initial, (initial + first) / 2, first, (first + second) / 2, second]
        np.testing.assert_allclose(result["values"][:5], expected, rtol=0, atol=1e-14)
        state = initial
        for index in range(80):
            state = state + .1 * np.array(independent_rhs(index / 10, state, DEBUG_THETA))
        np.testing.assert_allclose(result["values"][-1], state, rtol=1e-14, atol=1e-14)
        self.assertEqual(result["times"], times)

    def test_noiseless_free_observations_and_measured_target(self):
        episode = Episode(DEBUG_THETA)
        observations = episode.tools.evidence()["observations"]
        self.assertEqual({(r["variable"], r["time"]) for r in observations},
                         {("x", 0), ("y", 0), ("x", 1), ("y", 1)})
        reference = solve_ivp(independent_rhs, (0, 8), [10, 5], args=(DEBUG_THETA,),
                              method="Radau", rtol=2e-12, atol=2e-14, dense_output=True)
        for record in observations:
            expected = reference.sol(record["time"])[("x", "y").index(record["variable"])]
            self.assertAlmostEqual(record["value"], expected, places=7)
            self.assertEqual(record["charge"], 0)
        self.assertEqual(episode.tools.get_status()["remaining"], 40)
        purchased = episode.tools.measure_target("y", .371)
        self.assertAlmostEqual(purchased["value"], reference.sol(.371)[1], places=7)
        repeat = episode.tools.measure_target("y", .371)
        self.assertEqual(repeat["value"], purchased["value"])
        self.assertEqual(repeat["record_id"], purchased["record_id"])
        self.assertEqual(repeat["charge"], 0)
        self.assertEqual(repeat["remaining"], 28)


class TestAccountingAndCache(unittest.TestCase):
    def test_full_solves_cached_and_additional_times_free(self):
        episode = Episode(DEBUG_THETA)
        for fidelity, price in (("low", 1), ("high", 8)):
            with self.subTest(fidelity=fidelity):
                method = getattr(episode.tools, f"simulate_{fidelity}")
                with patch.object(env, f"_solve_{fidelity}", wraps=getattr(env, f"_solve_{fidelity}")) as solver:
                    first = method(list(DEBUG_THETA), [.25])
                    again = method(np.array(DEBUG_THETA), [8, 0, 1.23, 8])
                    default = method(DEBUG_THETA)
                self.assertEqual(solver.call_count, 1)
                self.assertEqual(first["charge"], price)
                self.assertFalse(first["cache_hit"])
                for result in (again, default):
                    self.assertEqual(result["result_id"], first["result_id"])
                    self.assertEqual(result["charge"], 0)
                    self.assertTrue(result["cache_hit"])
                self.assertEqual(again["times"], [8, 0, 1.23, 8])
                np.testing.assert_array_equal(again["values"][0], again["values"][3])
                self.assertEqual(default["times"], list(Config().working_times))
        self.assertEqual(episode.tools.get_status()["spent"], 9)

    def test_cache_uses_exact_parameters_and_separates_fidelity(self):
        episode = Episode(DEBUG_THETA)
        first = episode.tools.simulate_low(DEBUG_THETA)
        nearby = [np.nextafter(1., 1.2), .08, 1.4]
        next_result = episode.tools.simulate_low(nearby)
        high = episode.tools.simulate_high(DEBUG_THETA)
        self.assertFalse(next_result["cache_hit"])
        self.assertFalse(high["cache_hit"])
        self.assertEqual(len({r["result_id"] for r in (first, next_result, high)}), 3)
        self.assertEqual(episode.tools.get_status()["spent"], 10)

    def test_full_cache_identity_contains_complete_config(self):
        episode = Episode(DEBUG_THETA)
        episode.tools.simulate_low(DEBUG_THETA)
        key = next(iter(episode._cache))
        self.assertEqual(key, (DEBUG_THETA, "low", Config()._cache_key(), env._SOLVER_KEY))
        for kwargs in ({"initial": (11, 5)}, {"budget": 39}, {"working_times": (1, 8)},
                       {"tolerance": .2}, {"costs": {"low": 2, "high": 8, "measurement": 12}},
                       {"ranges": ((.7, 1.2), (.06, .10), (1.1, 1.7))}):
            with self.subTest(kwargs=kwargs):
                self.assertNotEqual(Config(**kwargs)._cache_key(), key[2])

    def test_ledgers_and_caches_are_episode_local(self):
        first, second = Episode(DEBUG_THETA), Episode(DEBUG_THETA)
        with patch.object(env, "_solve_low", wraps=env._solve_low) as solver:
            a = first.tools.simulate_low(DEBUG_THETA)
            b = second.tools.simulate_low(DEBUG_THETA)
        self.assertEqual(solver.call_count, 2)
        self.assertEqual(a["charge"], 1)
        self.assertEqual(b["charge"], 1)
        first.tools.measure_target("x", 2)
        self.assertEqual(first.tools.get_status()["spent"], 13)
        self.assertEqual(second.tools.get_status()["spent"], 1)
        self.assertEqual(len(second.tools.evidence()["observations"]), 4)

    def test_exact_budget_and_all_failed_or_successful_charges(self):
        episode = Episode(DEBUG_THETA)
        results = [episode.tools.simulate_high(DEBUG_THETA),
                   episode.tools.simulate_high([.9, .07, 1.2]),
                   episode.tools.measure_target("x", 2), episode.tools.measure_target("y", 2)]
        self.assertEqual([r["charge"] for r in results], [8, 8, 12, 12])
        self.assertEqual(episode.tools.get_status()["remaining"], 0)
        with patch.object(env, "_solve_low") as solver:
            rejected = episode.tools.simulate_low(DEBUG_THETA)
        solver.assert_not_called()
        self.assertEqual(rejected["status"], "unaffordable")
        self.assertEqual(rejected["charge"], 0)
        self.assertEqual(episode.tools.simulate_high(DEBUG_THETA, [.02])["charge"], 0)
        self.assertEqual(episode.tools.measure_target("x", 2)["charge"], 0)
        self.assertEqual(episode.tools.measure_target("x", 1)["charge"], 0)
        self.assertEqual(len(episode.tools.get_status()["ledger"]), 4)

    def test_unaffordable_request_does_not_execute_or_cache(self):
        episode = Episode(DEBUG_THETA, Config(budget=7))
        with patch.object(env, "_solve_high") as high, patch.object(episode._target, "sample") as target:
            for _ in range(5):
                self.assertEqual(episode.tools.simulate_high(DEBUG_THETA)["status"], "unaffordable")
                self.assertEqual(episode.tools.measure_target("x", 2)["status"], "unaffordable")
            high.assert_not_called()
            target.assert_not_called()
        self.assertEqual(episode.tools.get_status()["remaining"], 7)
        self.assertEqual(episode.tools.evidence()["simulations"], [])
        self.assertEqual(episode.tools.get_status()["ledger"], [])

    def test_failure_is_charged_once_cached_and_present_in_evidence(self):
        for fidelity, price in (("low", 1), ("high", 8)):
            with self.subTest(fidelity=fidelity):
                episode = Episode(DEBUG_THETA, Config(budget=price))
                method = getattr(episode.tools, f"simulate_{fidelity}")
                with patch.object(env, f"_solve_{fidelity}", side_effect=RuntimeError("private failure")) as solver:
                    first = method(DEBUG_THETA, [.5])
                    second = method(DEBUG_THETA, [7.77])
                self.assertEqual(solver.call_count, 1)
                self.assertEqual(first["status"], "failed")
                self.assertEqual(first["charge"], price)
                self.assertEqual(second["charge"], 0)
                self.assertTrue(second["cache_hit"])
                self.assertEqual(second["result_id"], first["result_id"])
                self.assertNotIn("private failure", json.dumps(first))
                self.assertEqual(episode.tools.get_status()["remaining"], 0)
                self.assertEqual(episode.tools.get_status()["simulations"], [])
                evidence = episode.tools.evidence()["simulations"]
                self.assertEqual(len(evidence), 1)
                self.assertEqual(evidence[0]["status"], "failed")
                self.assertEqual(evidence[0]["times"], list(Config().working_times))
                self.assertEqual(evidence[0]["values"], [])
                self.assertEqual(episode.tools.get_status()["ledger"][0]["status"], "failed")

    def test_unsuccessful_high_solver_is_a_charged_failure(self):
        events = []
        episode = Episode(DEBUG_THETA, log=lambda kind, **data: events.append((kind, data)))
        failed = SimpleNamespace(success=False, sol=None, t=np.array([0., .1]),
                                 y=np.array([[10., np.nan], [5., 4.]]), message="step failure")
        with patch.object(env, "solve_ivp", return_value=failed) as solver:
            result = episode.tools.simulate_high(DEBUG_THETA)
            repeat = episode.tools.simulate_high(DEBUG_THETA, [8])
        self.assertEqual(solver.call_count, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["charge"], 8)
        self.assertEqual(repeat["charge"], 0)
        first_event = [data for kind, data in events if kind == "simulation"][0]
        self.assertIsNone(first_event["artifact"]["values"][1][0])
        strict_json(events)

    def test_bad_dense_output_is_also_a_cached_failure(self):
        episode = Episode(DEBUG_THETA)
        bad = env._Trajectory(np.array([0, 8]), np.array([[10, 5], [10, 5]]),
                              dense=lambda times: np.full((2, len(times)), np.nan))
        with patch.object(env, "_solve_high", return_value=bad) as solver:
            result = episode.tools.simulate_high(DEBUG_THETA)
            again = episode.tools.simulate_high(DEBUG_THETA)
        self.assertEqual(solver.call_count, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(again["remaining"], 32)

    def test_measurement_failure_is_charged_and_repeat_is_free(self):
        episode = Episode(DEBUG_THETA)
        with patch.object(episode._target, "sample", side_effect=RuntimeError("test")) as sampler:
            first = episode.tools.measure_target("x", 2)
            again = episode.tools.measure_target("x", 2)
        self.assertEqual(sampler.call_count, 1)
        self.assertEqual(first["status"], "failed")
        self.assertEqual(first["charge"], 12)
        self.assertEqual(again["charge"], 0)
        self.assertEqual(episode.tools.get_status()["remaining"], 28)
        self.assertEqual(len(episode.tools.evidence()["observations"]), 4)

    def test_concurrent_identical_calls_are_charged_once(self):
        episode = Episode(DEBUG_THETA)
        with patch.object(env, "_solve_low", wraps=env._solve_low) as solver:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: episode.tools.simulate_low(DEBUG_THETA), range(8)))
        self.assertEqual(solver.call_count, 1)
        self.assertEqual(sum(r["charge"] for r in results), 1)
        self.assertEqual(sum(r["cache_hit"] for r in results), 7)


class TestValidationAndEvidence(unittest.TestCase):
    def test_repeated_invalid_simulations_do_not_execute_spend_or_cache(self):
        episode = Episode(DEBUG_THETA)
        bad_theta = [None, [], [1, .08], [1, .08, 1.4, 0], "1,.08,1.4",
                     [True, .08, 1.4], [np.bool_(True), .08, 1.4], ["1", .08, 1.4],
                     [float("nan"), .08, 1.4], [float("inf"), .08, 1.4],
                     [1 + 0j, .08, 1.4], [10 ** 400, .08, 1.4],
                     [.79, .08, 1.4], [1, .101, 1.4], [1, .08, 1.71], [[1], [.08], [1.4]]]
        bad_times = [[], "1", 1, [-.001], [8.01], [True], ["1"], [float("nan")],
                     [float("inf")], [[1]], {"time": 1}, [10 ** 400]]
        with patch.object(env, "_solve_low") as solver:
            for _ in range(3):
                for theta in bad_theta:
                    with self.subTest(theta=theta):
                        result = episode.tools.simulate_low(theta)
                        self.assertEqual(result["status"], "invalid")
                        self.assertEqual(result["charge"], 0)
                        strict_json(result)
                for times in bad_times:
                    with self.subTest(times=times):
                        result = episode.tools.simulate_low(DEBUG_THETA, times)
                        self.assertEqual(result["status"], "invalid")
                        strict_json(result)
            solver.assert_not_called()
        self.assertEqual(episode.tools.get_status()["remaining"], 40)
        self.assertEqual(episode.tools.get_status()["ledger"], [])
        self.assertEqual(episode.tools.evidence()["simulations"], [])

    def test_inclusive_parameter_bounds_are_valid(self):
        episode = Episode(DEBUG_THETA)
        for theta in product(*Config().ranges):
            with self.subTest(theta=theta):
                self.assertEqual(episode.tools.simulate_low(theta)["status"], "success")
        self.assertEqual(episode.tools.get_status()["spent"], 8)

    def test_invalid_measurements_and_submissions_do_not_close_episode(self):
        episode = Episode(DEBUG_THETA)
        for variable, time in [("z", 1), (0, 1), ([], 1), ("x", -1), ("x", 9),
                               ("x", True), ("x", "1"), ("x", float("nan"))]:
            with self.subTest(variable=variable, time=time):
                result = episode.tools.measure_target(variable, time)
                self.assertEqual(result["status"], "invalid")
                strict_json(result)
        for theta in ([], [1, .08, 99], [1, .08, float("nan")], [True, .08, 1.4]):
            self.assertEqual(episode.tools.submit(theta)["status"], "invalid")
        self.assertEqual(episode.tools.get_status()["status"], "active")
        self.assertEqual(episode.tools.get_status()["spent"], 0)
        self.assertEqual(episode.tools.submit(DEBUG_THETA)["status"], "submitted")

    def test_evidence_is_fixed_grid_even_after_arbitrary_time_requests(self):
        episode = Episode(DEBUG_THETA)
        first = episode.tools.simulate_low(DEBUG_THETA, [.125])
        baseline = episode.tools.evidence()["simulations"][0]
        episode.tools.simulate_low(DEBUG_THETA, [7.777])
        later = episode.tools.evidence()["simulations"][0]
        self.assertEqual(baseline, later)
        self.assertEqual(later["times"], list(Config().working_times))
        self.assertEqual(np.asarray(later["values"]).shape, (16, 2))
        self.assertEqual(later["result_id"], first["result_id"])
        self.assertEqual(episode.tools.get_status()["simulations"], [baseline])

    def test_public_copies_do_not_mutate_private_evidence_or_accounting(self):
        episode = Episode(DEBUG_THETA)
        result = episode.tools.simulate_low(DEBUG_THETA)
        result["values"][0][0] = -999
        result["theta"][0] = -999
        observation = episode.tools.measure_target("x", 2)
        observation["value"] = -999
        status = episode.tools.get_status()
        status["ledger"][0]["charge"] = 1000
        status["simulations"][0]["values"][0][0] = -999
        status["observations"][0]["value"] = -999
        config = episode.tools.public_config
        config["costs"]["low"] = 0
        clean = episode.tools.get_status()
        self.assertEqual(clean["spent"], 13)
        self.assertGreater(clean["simulations"][0]["values"][0][0], 0)
        self.assertEqual(clean["simulations"][0]["theta"], list(DEBUG_THETA))
        self.assertGreater(clean["observations"][-1]["value"], 0)
        self.assertEqual(clean["observations"][0]["value"], 10)
        self.assertEqual(episode.tools.public_config["costs"]["low"], 1)

    def test_facade_exposes_only_allowed_actions_and_no_private_score(self):
        episode = Episode(DEBUG_THETA)
        names = {name for name in dir(episode.tools) if not name.startswith("_")}
        self.assertEqual(names, {"simulate_low", "simulate_high", "measure_target", "get_status",
                                 "compare_cached_candidates", "submit", "evidence", "public_config"})
        self.assertIsInstance(episode.tools, PublicTools)
        payload = json.dumps(episode.tools.get_status())
        for forbidden in ("theta_true", "target_artifact", "DOP853", "rtol", "rhs", "score"):
            self.assertNotIn(forbidden, payload)

    def test_comparison_uses_purchased_evidence_without_solving_or_truth(self):
        episode = Episode(DEBUG_THETA)
        correct = episode.tools.simulate_high(DEBUG_THETA, [.25])
        episode.tools.simulate_low([.8, .06, 1.1])
        episode.tools.measure_target("x", 2.37)
        before = episode.tools.get_status()
        with patch.object(env, "_solve_high", side_effect=AssertionError("no solve")), \
                patch.object(env, "_solve_low", side_effect=AssertionError("no solve")), \
                patch.object(episode._target, "sample", side_effect=AssertionError("no target")), \
                patch.object(episode, "evaluate", side_effect=AssertionError("no score")):
            comparison = episode.tools.compare_cached_candidates()
        self.assertEqual(comparison["candidates"][0]["result_id"], correct["result_id"])
        self.assertEqual(comparison["candidates"][0]["normalized_rmse"], 0)
        self.assertEqual(len(comparison["candidates"][0]["predictions"]), 5)
        self.assertEqual(episode.tools.get_status(), before)
        strict_json(comparison)

    def test_empty_comparison_is_free(self):
        episode = Episode(DEBUG_THETA, Config(budget=0))
        result = episode.tools.compare_cached_candidates()
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["charge"], 0)
        self.assertEqual(result["remaining"], 0)


class TestScoringAndLogs(unittest.TestCase):
    def test_correct_submission_and_public_acknowledgment(self):
        episode = Episode(DEBUG_THETA)
        with patch.object(episode, "evaluate", side_effect=AssertionError("public must not score")):
            result = episode.tools.submit(DEBUG_THETA)
        self.assertEqual(set(result), {"status", "theta_hat", "charge", "remaining"})
        score = episode.evaluate()
        self.assertEqual(score["errors"], [0, 0, 0])
        self.assertEqual(score["parameter_error"], 0)
        self.assertTrue(score["success"])
        self.assertTrue(score["valid"])
        self.assertEqual(score["score"], 1)

    def test_normalization_and_all_parameter_success(self):
        episode = Episode(DEBUG_THETA)
        episode.tools.submit([1.05, .096, 1.33])
        score = episode.evaluate()
        np.testing.assert_allclose(score["errors"], [.5, 2, .5], rtol=1e-14)
        self.assertAlmostEqual(score["parameter_error"], 2)
        self.assertEqual(score["successes"], [True, False, True])
        self.assertFalse(score["success"])
        self.assertEqual(score["score"], 0)

    def test_roundoff_at_both_inclusive_boundaries(self):
        for factors in product((.9, 1.1), repeat=3):
            with self.subTest(factors=factors):
                episode = Episode(DEBUG_THETA)
                episode.tools.submit(np.array(DEBUG_THETA) * factors)
                score = episode.evaluate()
                self.assertTrue(score["success"])
                self.assertLessEqual(score["parameter_error"], 1)
                np.testing.assert_allclose(score["errors"], [1, 1, 1], rtol=1e-14)

    def test_a_meaningfully_outside_estimate_fails(self):
        for index in range(3):
            with self.subTest(index=index):
                estimate = list(DEBUG_THETA)
                estimate[index] *= 1.1 + 1e-10
                episode = Episode(DEBUG_THETA)
                episode.tools.submit(estimate)
                score = episode.evaluate()
                self.assertFalse(score["success"])
                self.assertGreater(score["parameter_error"], 1)

    def test_no_savings_bonus(self):
        first, second = Episode(DEBUG_THETA), Episode(DEBUG_THETA)
        second.tools.measure_target("x", 3)
        for episode in (first, second):
            episode.tools.submit(DEBUG_THETA)
        a, b = first.evaluate(), second.evaluate()
        self.assertEqual(a["score"], b["score"])
        self.assertEqual(a["parameter_error"], b["parameter_error"])
        self.assertNotEqual(a["remaining"], b["remaining"])

    def test_abort_unsubmitted_and_repeated_evaluation(self):
        episode = Episode(DEBUG_THETA)
        active = episode.evaluate()
        self.assertFalse(active["valid"])
        self.assertEqual(active["errors"], [None] * 3)
        self.assertEqual(active["score"], 0)
        episode.tools.simulate_low(DEBUG_THETA)
        episode.abort("runtime expired")
        episode.abort("second abort")
        score = episode.evaluate()
        self.assertEqual(score["status"], "aborted")
        self.assertEqual(score["abort_reason"], "runtime expired")
        self.assertEqual(score["spent"], 1)
        self.assertFalse(score["valid"])
        self.assertEqual(score, episode.evaluate())
        strict_json(score)

    def test_submission_is_terminal_and_cannot_be_replaced(self):
        episode = Episode(DEBUG_THETA)
        episode.tools.submit(DEBUG_THETA)
        for result in (episode.tools.submit([.8, .06, 1.1]),
                       episode.tools.simulate_low(DEBUG_THETA),
                       episode.tools.simulate_high(DEBUG_THETA),
                       episode.tools.measure_target("x", 2)):
            self.assertEqual(result["status"], "closed")
            self.assertEqual(result["charge"], 0)
        episode.abort("late abort")
        self.assertEqual(episode.evaluate()["theta_hat"], list(DEBUG_THETA))
        self.assertEqual(episode.evaluate()["status"], "submitted")

    def test_log_artifacts_reconstruct_the_entire_solved_trajectory(self):
        events = []
        episode = Episode(DEBUG_THETA, log=lambda kind, **data: events.append((kind, data)))
        episode.tools.simulate_low(DEBUG_THETA, [.25])
        expected = episode.tools.simulate_high(DEBUG_THETA, [0, .1234, 2.3456, 8])
        episode.tools.measure_target("x", 4)
        episode.tools.simulate_high(DEBUG_THETA, [7])
        episode.tools.submit(DEBUG_THETA)
        episode.evaluate()
        persisted = strict_json(events)
        self.assertEqual(persisted[0][0], "episode_started")
        self.assertEqual(persisted[0][1]["theta_true"], list(DEBUG_THETA))
        simulations = [data for kind, data in persisted if kind == "simulation"]
        low, high, repeat = [data["artifact"] for data in simulations]
        self.assertEqual(len(low["times"]), 81)
        self.assertEqual(len(low["values"]), 81)
        self.assertEqual(low["times"][-1], 8)
        self.assertIsNone(repeat)
        reconstructed = []
        for time in expected["times"]:
            segment = next(s for s in high["segments"] if s["t_old"] <= time <= s["t"])
            fraction = (time - segment["t_old"]) / segment["h"]
            value = np.zeros(2)
            for index, coefficient in enumerate(reversed(segment["F"])):
                value += coefficient
                value *= fraction if index % 2 == 0 else 1 - fraction
            reconstructed.append(value + segment["y_old"])
        np.testing.assert_allclose(reconstructed, expected["values"], rtol=0, atol=1e-13)

    def test_logger_mutation_or_exception_cannot_undo_charged_work(self):
        def logger(kind, **data):
            if kind == "simulation":
                data["result"]["theta"][0] = 999
                raise RuntimeError("logger unavailable")

        episode = Episode(DEBUG_THETA, log=logger)
        with self.assertRaisesRegex(RuntimeError, "logger unavailable"):
            episode.tools.simulate_low(DEBUG_THETA)
        evidence = episode.tools.evidence()
        self.assertEqual(evidence["simulations"][0]["theta"], list(DEBUG_THETA))
        self.assertEqual(episode.tools.get_status()["spent"], 1)
        with patch.object(env, "_solve_low") as solver:
            result = episode.tools.simulate_low(DEBUG_THETA)
        solver.assert_not_called()
        self.assertEqual(result["status"], "closed")
        self.assertEqual(episode.tools.get_status()["status"], "aborted")
        self.assertEqual(episode.evaluate()["abort_reason"], "log callback failed")
        self.assertEqual(episode.tools.get_status()["spent"], 1)

    def test_charge_and_validated_arguments_precede_execution(self):
        events = []
        episode = Episode(DEBUG_THETA, log=lambda kind, **data: events.append((kind, data)))
        real_solver = env._solve_low

        def solver(theta, config):
            self.assertEqual(events[-1][0], "charged")
            charge = events[-1][1]
            self.assertEqual(charge["entry"]["charge"], 1)
            self.assertEqual(charge["entry"]["status"], "pending")
            self.assertEqual(charge["budget_after"]["remaining"], 39)
            self.assertEqual(charge["budget_after"]["ledger"][0]["charge"], 1)
            started = [data for kind, data in events if kind == "tool_started"][-1]
            self.assertEqual(started["arguments"]["theta"], list(DEBUG_THETA))
            self.assertEqual(started["arguments"]["times"], [.123])
            return real_solver(theta, config)

        with patch.object(env, "_solve_low", side_effect=solver):
            episode.tools.simulate_low(DEBUG_THETA, [.123])
        strict_json(events)

    def test_logging_failure_before_execution_prevents_paid_work_and_resume(self):
        for failure_event, expected_charge in (("tool_call", 0), ("tool_started", 0), ("charged", 1)):
            with self.subTest(failure_event=failure_event):
                def logger(kind, **data):
                    if kind == failure_event:
                        raise RuntimeError("log unavailable")
                episode = Episode(DEBUG_THETA, log=logger)
                with patch.object(env, "_solve_low") as solver:
                    with self.assertRaisesRegex(RuntimeError, "log unavailable"):
                        episode.tools.simulate_low(DEBUG_THETA)
                    result = episode.tools.simulate_low(DEBUG_THETA)
                solver.assert_not_called()
                self.assertEqual(result["status"], "closed")
                self.assertEqual(episode.tools.get_status()["spent"], expected_charge)
                self.assertEqual(episode.tools.get_status()["status"], "aborted")
                self.assertFalse(episode.evaluate()["valid"])

    def test_simulator_interruption_still_has_charge_and_arguments_in_log(self):
        events = []
        episode = Episode(DEBUG_THETA, log=lambda kind, **data: events.append((kind, data)))
        with patch.object(env, "_solve_low", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            episode.tools.simulate_low(DEBUG_THETA, [.75])
        self.assertEqual(events[-1][0], "charged")
        self.assertEqual(events[-1][1]["budget_after"]["spent"], 1)
        self.assertEqual(events[-2][0], "tool_started")
        self.assertEqual(events[-2][1]["arguments"]["times"], [.75])
        episode.abort("interrupted")
        self.assertEqual(episode.evaluate()["spent"], 1)

    def test_partial_euler_failure_artifact_contains_only_completed_finite_nodes(self):
        events = []
        episode = Episode(DEBUG_THETA, log=lambda kind, **data: events.append((kind, data)))
        rhs = env._rhs
        calls = 0

        def fail_after_two_steps(time, state, theta):
            nonlocal calls
            calls += 1
            if calls == 3:
                return np.array([float("nan"), float("inf")])
            return rhs(time, state, theta)

        with patch.object(env, "_rhs", side_effect=fail_after_two_steps):
            result = episode.tools.simulate_low(DEBUG_THETA)
        self.assertEqual(result["status"], "failed")
        artifact = next(data["artifact"] for kind, data in events if kind == "simulation")
        self.assertEqual(artifact["times"], [0, .1, .2])
        self.assertEqual(len(artifact["values"]), 3)
        self.assertTrue(np.all(np.isfinite(artifact["values"])))
        strict_json(events)

    def test_all_free_facade_accesses_are_logged_without_recursion(self):
        events = []
        episode = Episode(DEBUG_THETA, log=lambda kind, **data: events.append((kind, data)))
        episode.tools.public_config
        episode.tools.get_status()
        episode.tools.evidence()
        episode.tools.compare_cached_candidates()
        expected = ["public_config", "get_status", "evidence", "compare_cached_candidates"]
        self.assertEqual([data["action"] for kind, data in events if kind == "tool_call"], expected)
        self.assertEqual([data["action"] for kind, data in events if kind == "tool_result"], expected)
        self.assertNotIn("charged", [kind for kind, _ in events])

    def test_invalid_error_and_trace_retain_json_safe_caller_arguments(self):
        events = []
        episode = Episode(DEBUG_THETA, log=lambda kind, **data: events.append((kind, data)))
        result = episode.tools.simulate_low([float("nan"), .08, 1.4], [-1, 9])
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["arguments"], {"theta": [{"type": "float", "value": "nan"}, .08, 1.4],
                                               "times": [-1, 9]})
        self.assertEqual(events[-1][1]["result"]["arguments"], result["arguments"])
        strict_json(events)

    def test_config_from_public_round_trips_for_spawn(self):
        config = Config(budget=17, initial=(11, 5))
        reconstructed = Config.from_public(strict_json(config.public()))
        self.assertEqual(config.public(), reconstructed.public())
        self.assertEqual(config._cache_key(), reconstructed._cache_key())
        with self.assertRaises(ValueError):
            Config.from_public({"budget": 17})

    def test_logger_can_read_status_without_recursive_trace(self):
        episode, events = None, []

        def logger(kind, **data):
            snapshot = episode.tools.get_status() if episode is not None else None
            events.append((kind, data, snapshot))

        episode = Episode(DEBUG_THETA, log=logger)
        episode.tools.simulate_low(DEBUG_THETA)
        self.assertEqual([kind for kind, _, _ in events],
                         ["episode_started", "tool_call", "tool_started", "charged", "simulation", "tool_result"])
        self.assertEqual(events[-1][2]["spent"], 1)
        strict_json(events)


if __name__ == "__main__":
    unittest.main()

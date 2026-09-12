"""CPU-only tests for the separate three-QoI numerical revision."""

from copy import deepcopy
from functools import lru_cache
from itertools import product
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from scipy.integrate import quad, solve_ivp

from budgeted_science.claim_verification import numerics as old
from budgeted_science.claim_verification_qoi import numerics as num


DEBUG = (1., .08, 1.4)
RUN_KEYS = {"status", "config", "times", "values", "internal", "rhs_evaluations",
            "output_samples", "work", "credits", "seconds"}


@lru_cache()
def debug_reference():
    return num.reference(DEBUG)


def strict_json(value):
    return json.loads(json.dumps(value, allow_nan=False))


class ConfigAndQuoteTests(unittest.TestCase):
    def test_imported_dynamics_and_constants_are_the_existing_ones(self):
        self.assertIs(num.rhs, old.rhs)
        self.assertIs(num.validate_theta, old.validate_theta)
        self.assertEqual(num.BOUNDS, old.BOUNDS)
        self.assertEqual(num.INITIAL, old.INITIAL)
        self.assertEqual(num.HORIZON, old.HORIZON)

    def test_default_configuration_has_exact_fields(self):
        settings = num.config()
        self.assertEqual(settings, {"method": "Euler", "dt": .08, "output_step": .08, "output_offset": 0})
        self.assertEqual(strict_json(settings), settings)
        self.assertEqual(num.config("RK2")["method"], "RK2")

    def test_step_and_schedule_boundary_values(self):
        for dt, spacing, phase in product((.01, .32, 8 / 37), (.01, 2), (0, np.nextafter(1., 0))):
            with self.subTest(dt=dt, spacing=spacing, phase=phase):
                settings = num.config("RK2", dt, spacing, phase)
                self.assertEqual(settings["dt"], dt)
                self.assertEqual(settings["output_offset"], phase)

    def test_invalid_configuration_values(self):
        cases = [{"method": "DOP853"}, {"method": "midpoint"}, {"method": []},
                 {"dt": .009}, {"dt": .321}, {"dt": .3}, {"dt": .08 + 1e-8},
                 {"dt": 0}, {"dt": True}, {"dt": np.bool_(True)}, {"dt": ".08"},
                 {"dt": float("nan")}, {"dt": float("inf")}, {"dt": 10 ** 400},
                 {"dt": .08 + 0j}, {"output_step": .009}, {"output_step": 2.01},
                 {"output_step": True}, {"output_step": float("nan")},
                 {"output_offset": -1e-9}, {"output_offset": 1}, {"output_offset": True},
                 {"output_offset": float("inf")}, {"output_offset": ".5"}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                num.config(**kwargs)

    def test_consumers_revalidate_exact_config_keys(self):
        good = num.config()
        for settings in (None, [], "Euler", {}, {**good, "rtol": 1e-10},
                         {key: value for key, value in good.items() if key != "dt"},
                         {**good, "method": "Radau"}, {**good, "dt": .3}):
            for operation in (num.output_times, num.quote, lambda value: num.solve(DEBUG, value)):
                with self.subTest(settings=settings, operation=operation), self.assertRaises(ValueError):
                    operation(settings)

    def test_phased_times_include_endpoints_once(self):
        np.testing.assert_array_equal(num.output_times(num.config(output_step=2)), [0, 2, 4, 6, 8])
        np.testing.assert_array_equal(num.output_times(num.config(output_step=2, output_offset=.5)),
                                      [0, 1, 3, 5, 7, 8])
        for spacing, phase in product((.01, .08, .3, 1.7, 2), (0, .25, .5, .75)):
            with self.subTest(spacing=spacing, phase=phase):
                times = np.array(num.output_times(num.config(output_step=spacing, output_offset=phase)))
                self.assertEqual(times[0], 0)
                self.assertEqual(times[-1], 8)
                self.assertTrue(np.all(np.diff(times) > 0))
                indices = (times[1:-1] - phase * spacing) / spacing
                np.testing.assert_allclose(indices, np.rint(indices), atol=2e-12, rtol=0)

    def test_output_schedule_is_independent_of_method_and_dt(self):
        expected = num.output_times(num.config("Euler", .08, .3, .75))
        for method, dt in product(("Euler", "RK2"), (.01, .04, .16, .32)):
            self.assertEqual(num.output_times(num.config(method, dt, .3, .75)), expected)

    def test_quotes_count_stages_and_actual_output_samples(self):
        self.assertEqual(num.quote(num.config()),
                         {"rhs_evaluations": 100, "output_samples": 101, "work": 201, "credits": 2.01})
        self.assertEqual(num.quote(num.config("RK2")),
                         {"rhs_evaluations": 200, "output_samples": 101, "work": 301, "credits": 3.01})
        self.assertEqual(num.quote(num.config("Euler", .32, 2, .5)),
                         {"rhs_evaluations": 25, "output_samples": 6, "work": 31, "credits": .31})
        with patch.object(num, "rhs") as rhs, patch.object(num, "solve_ivp") as solver:
            num.quote(num.config("RK2", .01, .01, .5))
            rhs.assert_not_called()
            solver.assert_not_called()


class NumericalExecutionTests(unittest.TestCase):
    def test_euler_matches_old_solver_and_interpolant(self):
        for dt, spacing, phase in ((.01, .08, 0), (.08, .03, .5), (.16, .7, .25), (.32, 2, .5)):
            with self.subTest(dt=dt, spacing=spacing, phase=phase):
                settings = num.config("Euler", dt, spacing, phase)
                new = num.solve(DEBUG, settings)
                legacy = old.solve(DEBUG, old.configuration("Euler", dt=dt, times=num.output_times(settings)))
                self.assertEqual(new["status"], "success")
                np.testing.assert_array_equal(new["times"], legacy["times"])
                np.testing.assert_array_equal(new["values"], legacy["values"])
                np.testing.assert_array_equal(new["internal"]["node_times"], legacy["internal"]["node_times"])
                np.testing.assert_array_equal(new["internal"]["node_values"], legacy["internal"]["node_values"])

    def test_rk2_is_explicit_midpoint(self):
        calls = []

        def linear_rhs(time, state, theta):
            if len(calls) < 2:
                calls.append((time, state.copy()))
            return np.asarray(state)

        with patch.object(num, "rhs", side_effect=linear_rhs):
            result = num.solve(DEBUG, num.config("RK2", .08))
        self.assertEqual(result["status"], "success")
        self.assertEqual(calls[0][0], 0)
        self.assertEqual(calls[1][0], .04)
        np.testing.assert_allclose(calls[1][1], np.array(num.INITIAL) * 1.04)
        np.testing.assert_allclose(result["internal"]["node_values"][1],
                                   np.array(num.INITIAL) * (1 + .08 + .08 ** 2 / 2))

    def test_rk2_second_order_convergence(self):
        reference = solve_ivp(old.rhs, (0, 8), num.INITIAL, args=(DEBUG,),
                              method="DOP853", rtol=1e-12, atol=1e-14).y[:, -1]
        errors = []
        for dt in (.08, .04, .02, .01):
            result = num.solve(DEBUG, num.config("RK2", dt))
            self.assertEqual(result["status"], "success")
            errors.append(float(np.max(np.abs(np.array(result["internal"]["node_values"][-1]) - reference))))
        for coarse, fine in zip(errors, errors[1:]):
            self.assertGreater(coarse / fine, 3.5)
            self.assertLess(coarse / fine, 4.5)

    def test_rk2_improves_same_step_accuracy(self):
        reference = debug_reference()["qois"]
        euler = num.qois(num.solve(DEBUG, num.config("Euler", .08, .01)))
        midpoint = num.qois(num.solve(DEBUG, num.config("RK2", .08, .01)))
        for name in ("peak_height", "cumulative"):
            self.assertLess(abs(midpoint[name] - reference[name]), abs(euler[name] - reference[name]) / 10)

    def test_rk2_output_is_linear_interpolation_of_its_own_nodes(self):
        settings = num.config("RK2", .08, .08, .5)
        result = num.solve(DEBUG, settings)
        self.assertEqual(result["times"][1], .04)
        expected = np.mean(np.array(result["internal"]["node_values"])[:2], axis=0)
        np.testing.assert_allclose(result["values"][1], expected, rtol=0, atol=1e-14)
        # Output resolution/phase does not alter the integrated trajectory.
        other = num.solve(DEBUG, num.config("RK2", .08, 2, 0))
        self.assertEqual(result["internal"], other["internal"])

    def test_success_schema_and_exact_accounting(self):
        for method, dt, step, offset in (("Euler", .08, .08, 0), ("RK2", .01, 2, .5),
                                         ("Euler", .32, .03, .25), ("RK2", .16, .1, .75)):
            with self.subTest(method=method, dt=dt):
                settings = num.config(method, dt, step, offset)
                with patch.object(num, "rhs", wraps=old.rhs) as rhs:
                    result = num.solve(DEBUG, settings)
                self.assertEqual(set(result), RUN_KEYS)
                self.assertEqual(result["status"], "success")
                self.assertEqual(set(result["internal"]), {"node_times", "node_values"})
                self.assertEqual(result["rhs_evaluations"], rhs.call_count)
                self.assertEqual({key: result[key] for key in num.quote(settings)}, num.quote(settings))
                self.assertGreaterEqual(result["seconds"], 0)
                self.assertEqual(result["times"][0], 0)
                self.assertEqual(result["times"][-1], 8)
                np.testing.assert_array_equal(result["values"][0], num.INITIAL)
                strict_json(result)

    def test_arguments_copied_and_no_reference_used(self):
        settings, theta = num.config(), list(DEBUG)
        before = deepcopy(settings)
        with patch.object(num, "reference", side_effect=AssertionError("no oracle")), \
                patch.object(num, "solve_ivp", side_effect=AssertionError("no adaptive solver")):
            result = num.solve(theta, settings)
        self.assertEqual(result["status"], "success")
        self.assertEqual(settings, before)
        self.assertEqual(theta, list(DEBUG))
        result["config"]["dt"] = 0
        self.assertEqual(settings, before)

    def test_invalid_arguments_raise_before_any_solver(self):
        invalid_theta = [None, [], [1, .08], [1, .08, 1.4, 2], "1,.08,1.4", {"x": 1},
                         [True, .08, 1.4], [np.bool_(True), .08, 1.4], ["1", .08, 1.4],
                         [np.nan, .08, 1.4], [np.inf, .08, 1.4], [10 ** 400, .08, 1.4],
                         [.59, .08, 1.4], [1, .121, 1.4], [1, .08, 2.01], [[1], [.08], [1.4]]]
        with patch.object(num, "rhs") as rhs, patch.object(num, "solve_ivp") as solver:
            for theta in invalid_theta:
                for operation in (lambda: num.solve(theta, num.config()), lambda: num.reference(theta)):
                    with self.subTest(theta=theta), self.assertRaises(ValueError):
                        operation()
            rhs.assert_not_called()
            solver.assert_not_called()

    def test_bounds_are_inclusive(self):
        for theta in product(*num.BOUNDS):
            with self.subTest(theta=theta):
                result = num.solve(theta, num.config("RK2", .01, 2))
                self.assertEqual(result["status"], "success")

    def test_euler_failure_keeps_finite_partial_nodes_and_actual_calls(self):
        calls = 0

        def failing_rhs(time, state, theta):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("mock numerical failure")
            return old.rhs(time, state, theta)

        with patch.object(num, "rhs", side_effect=failing_rhs):
            result = num.solve(DEBUG, num.config())
        self.assertEqual(set(result), RUN_KEYS)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["rhs_evaluations"], 3)
        self.assertEqual(result["output_samples"], 0)
        self.assertEqual(result["work"], 3)
        self.assertEqual(result["credits"], .03)
        self.assertEqual(result["times"], [])
        self.assertEqual(result["values"], [])
        self.assertEqual(result["internal"]["node_times"], [0, .08, .16])
        self.assertTrue(np.all(np.isfinite(result["internal"]["node_values"])))
        strict_json(result)

    def test_rk2_failed_second_stage_counts_both_calls(self):
        with patch.object(num, "rhs", side_effect=[np.zeros(2), FloatingPointError("second stage")]) as rhs:
            result = num.solve(DEBUG, num.config("RK2"))
        self.assertEqual(rhs.call_count, 2)
        self.assertEqual(result["rhs_evaluations"], 2)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["internal"]["node_values"], [list(num.INITIAL)])
        self.assertEqual(result["credits"], .02)

    def test_rk2_invalid_midpoint_does_not_charge_unattempted_stage(self):
        with patch.object(num, "rhs", return_value=[-1000, 0]) as rhs:
            result = num.solve(DEBUG, num.config("RK2"))
        self.assertEqual(rhs.call_count, 1)
        self.assertEqual(result["rhs_evaluations"], 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["output_samples"], 0)

    def test_nonfinite_or_negative_results_are_failed_finite_artifacts(self):
        for derivative in ([np.nan, 0], [np.inf, 0], [-1000, 0], [1, 2, 3]):
            with self.subTest(derivative=derivative), patch.object(num, "rhs", return_value=derivative):
                result = num.solve(DEBUG, num.config())
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["work"], 1)
                self.assertEqual(result["internal"]["node_values"], [list(num.INITIAL)])
                strict_json(result)

    def test_output_failure_keeps_integration_but_no_output_charge(self):
        for failure in (RuntimeError("sampling failed"), None):
            kwargs = {"side_effect": failure} if failure is not None else {"return_value": [[np.nan, 1]]}
            with self.subTest(failure=failure), patch.object(num, "_sample", **kwargs):
                result = num.solve(DEBUG, num.config("RK2"))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["rhs_evaluations"], 200)
            self.assertEqual(result["output_samples"], 0)
            self.assertEqual(result["work"], 200)
            self.assertEqual(len(result["internal"]["node_values"]), 101)
            self.assertEqual(result["times"], [])
            strict_json(result)


class QoiTests(unittest.TestCase):
    def test_irregular_trapezoids_and_earliest_tied_peak(self):
        fixture = {"status": "success", "times": [0, 1, 3, 8],
                   "values": [[2, 5], [4, 3], [4, 8], [1, 2]]}
        self.assertEqual(num.qois(fixture), {"peak_height": 4, "peak_time": 1, "cumulative": 23.5})

    def test_endpoints_and_zero_population_are_valid_qois(self):
        for values, height, at, cumulative in (([[3, 0], [1, 0]], 3, 0, 16),
                                               ([[1, 0], [3, 0]], 3, 8, 16),
                                               ([[0, 0], [0, 0]], 0, 0, 0)):
            result = num.qois({"status": "success", "times": [0, 8], "values": values})
            self.assertEqual(result, {"peak_height": height, "peak_time": at, "cumulative": cumulative})

    def test_only_successful_finite_nonnegative_consistent_data_accepted(self):
        fixture = {"status": "success", "times": [0, 1, 8], "values": [[1, 2], [2, 3], [1, 0]]}
        changes = [{"status": "failed"}, {"times": []}, {"times": [0, 1]}, {"times": [0, 1, np.nan]},
                   {"times": [0, 1, np.inf]}, {"times": [-1, 1, 8]}, {"times": [0, 1, 9]},
                   {"times": [0, 1, 1]}, {"times": [0, 8, 1]}, {"times": [[0, 1, 8]]},
                   {"values": [[1], [2], [3]]}, {"values": [[-1, 2], [2, 3], [1, 0]]},
                   {"values": [[1, 2], [2, np.nan], [1, 0]]},
                   {"values": [[np.inf, 2], [2, 3], [1, 0]]},
                   {"values": [[1e308, 0], [1e308, 0], [1e308, 0]]}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                num.qois({**fixture, **change})
        for incomplete in (None, {}, {"status": "success"}):
            with self.assertRaises(ValueError):
                num.qois(incomplete)

    def test_qois_only_use_stored_outputs(self):
        fixture = {"status": "success", "times": [0, 1, 8], "values": [[1, 2], [2, 3], [1, 0]],
                   "internal": {"node_times": [0, .5, 8], "node_values": [[1, 2], [1000, 2], [1, 2]]}}
        with patch.object(num, "rhs", side_effect=AssertionError("no solve")), \
                patch.object(num, "reference", side_effect=AssertionError("no reference")):
            result = num.qois(fixture)
        self.assertEqual(result["peak_height"], 2)
        self.assertEqual(result["peak_time"], 1)


class ReferenceTests(unittest.TestCase):
    def test_four_independent_method_and_search_checks(self):
        result = debug_reference()
        self.assertEqual(set(result), {"qois", "checks", "peak_time_eligible", "peak_time_reason", "regime_diagnostics"})
        checks = result["checks"]
        self.assertTrue(checks["passed"])
        self.assertEqual({(c["method"], c["search_points"]) for c in checks["comparisons"]},
                         set(product(("DOP853", "Radau"), (4097, 8193))))
        self.assertLess(checks["peak_height_relative_agreement"], 1e-7)
        self.assertLess(checks["peak_time_absolute_agreement"], 1e-6)
        self.assertLess(checks["cumulative_relative_agreement"], 1e-7)
        self.assertLess(checks["augmented_vs_quad_relative_agreement"], 1e-7)
        self.assertEqual(checks["rtol"], 1e-11)
        self.assertEqual(checks["atol"], 1e-13)
        strict_json(result)

    def test_debug_reference_matches_existing_peak_and_known_integral(self):
        result = debug_reference()["qois"]
        self.assertAlmostEqual(result["peak_height"], 33.810319694, places=7)
        self.assertAlmostEqual(result["peak_time"], 2.767580270, places=7)
        self.assertAlmostEqual(result["cumulative"], 158.982849334, places=7)

    def test_both_solvers_augment_integral_and_quad_runs_independently(self):
        with patch.object(num, "solve_ivp", wraps=solve_ivp) as solver, \
                patch.object(num, "quad", wraps=quad) as quadrature:
            result = num.reference(DEBUG)
        self.assertEqual(solver.call_count, 2)
        self.assertEqual(quadrature.call_count, 2)
        self.assertEqual([call.kwargs["method"] for call in solver.call_args_list], ["DOP853", "Radau"])
        for call in solver.call_args_list:
            self.assertEqual(call.args[2], (10, 5, 0))
            self.assertEqual(call.kwargs["rtol"], 1e-11)
            self.assertEqual(call.kwargs["atol"], 1e-13)
            self.assertTrue(call.kwargs["dense_output"])
            np.testing.assert_allclose(call.args[0](0, np.array([10, 5, 0]), DEBUG), [5, -3.4, 10])
        self.assertLess(result["checks"]["augmented_vs_quad_relative_agreement"], 1e-7)

    def test_debug_peak_is_unique_interior_and_sufficiently_sharp(self):
        result = debug_reference()
        self.assertTrue(result["peak_time_eligible"])
        self.assertEqual(result["peak_time_reason"], "unique_well_separated_interior_maximum")
        diagnostic = result["regime_diagnostics"]
        self.assertEqual(diagnostic["interior_maxima_count"], 1)
        self.assertGreater(diagnostic["max_abs_dx_dt"], 0)
        self.assertGreaterEqual(diagnostic["relative_peak_separation"], 1e-4)
        self.assertGreaterEqual(diagnostic["local_drop_left"], 1e-7)
        self.assertGreaterEqual(diagnostic["local_drop_right"], 1e-7)
        self.assertEqual(diagnostic["local_distance"], .02)

    def test_endpoint_peak_is_not_time_eligible(self):
        result = num.reference((.6, .12, .8))
        self.assertEqual(result["qois"]["peak_time"], 0)
        self.assertFalse(result["peak_time_eligible"])
        self.assertEqual(result["peak_time_reason"], "endpoint_global_maximum")
        self.assertEqual(result["regime_diagnostics"]["interior_maxima_count"], 0)

    def test_flat_equilibrium_is_not_time_eligible(self):
        result = num.reference((.6, .1, .9))
        self.assertFalse(result["peak_time_eligible"])
        self.assertEqual(result["peak_time_reason"], "flat_trajectory")
        self.assertAlmostEqual(result["qois"]["peak_height"], 10, places=10)
        self.assertAlmostEqual(result["qois"]["cumulative"], 80, places=10)
        self.assertLess(result["regime_diagnostics"]["max_abs_dx_dt"], 1e-10)

    def _analytic_extrema(self, x, dx):
        def sample(time):
            t = np.asarray(time)
            return np.array([x(t), np.full_like(t, 5.), np.zeros_like(t)])

        def rhs(time, state, theta):
            t = np.asarray(time)
            return np.array([dx(t), np.zeros_like(t)])

        with patch.object(num, "rhs", side_effect=rhs):
            return num._extrema(SimpleNamespace(sol=sample), DEBUG, 8193)

    def test_equal_competing_interior_maxima_are_ineligible(self):
        omega = np.pi / 2
        peak, diagnostic, reason = self._analytic_extrema(
            lambda t: 10 + np.cos(omega * (t - 2)),
            lambda t: -omega * np.sin(omega * (t - 2)))
        self.assertAlmostEqual(peak["peak_time"], 2, places=10)
        self.assertEqual(diagnostic["interior_maxima_count"], 2)
        self.assertAlmostEqual(diagnostic["relative_peak_separation"], 0, places=10)
        self.assertEqual(reason, "competing_maxima")

    def test_interior_global_maximum_can_fail_local_flatness(self):
        omega = np.pi / 4
        peak, diagnostic, reason = self._analytic_extrema(
            lambda t: 10 + .001 * np.cos(omega * (t - 4)),
            lambda t: -.001 * omega * np.sin(omega * (t - 4)))
        self.assertAlmostEqual(peak["peak_time"], 4, places=10)
        self.assertGreater(diagnostic["relative_peak_separation"], 1e-4)
        self.assertLess(diagnostic["local_drop_left"], 1e-7)
        self.assertEqual(reason, "insufficient_local_drop")

    def test_near_endpoint_maximum_lacks_two_sided_flatness_window(self):
        peak, diagnostic, reason = self._analytic_extrema(
            lambda t: 10 + np.exp(-((t - .01) / .02) ** 2),
            lambda t: -2 * (t - .01) / .02 ** 2 * np.exp(-((t - .01) / .02) ** 2))
        self.assertAlmostEqual(peak["peak_time"], .01, places=10)
        self.assertIsNone(diagnostic["local_drop_left"])
        self.assertEqual(reason, "insufficient_interior_margin")

    def test_disagreeing_height_or_time_references_are_rejected(self):
        real_extrema = num._extrema
        for key, increment in (("peak_height", .001), ("peak_time", .001)):
            calls = 0

            def disagree(*args):
                nonlocal calls
                calls += 1
                peak, diagnostic, reason = real_extrema(*args)
                if calls > 2:
                    peak[key] += increment
                return peak, diagnostic, reason

            with self.subTest(key=key), patch.object(num, "_extrema", side_effect=disagree), \
                    self.assertRaisesRegex(RuntimeError, "references disagree"):
                num.reference(DEBUG)

    def test_disagreeing_quadrature_is_rejected(self):
        def disagree(*args, **kwargs):
            value, error = quad(*args, **kwargs)
            return value * 1.001, error

        with patch.object(num, "quad", side_effect=disagree), self.assertRaisesRegex(RuntimeError, "references disagree"):
            num.reference(DEBUG)

    def test_unsuccessful_reference_solver_is_not_accepted(self):
        failed = SimpleNamespace(success=False, sol=None)
        with patch.object(num, "solve_ivp", return_value=failed), self.assertRaises(RuntimeError):
            num.reference(DEBUG)


if __name__ == "__main__":
    unittest.main()

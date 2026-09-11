"""Opt-in amplitude extension: numerical contracts, not an agent evaluation."""

from fractions import Fraction
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.burgers.budget import BudgetExceeded, Ledger, WORK_PER_CREDIT
from budgeted_science.burgers.cache import SimulationCache, SimulationService, cache_key
from budgeted_science.burgers.config import (
    FORECAST_POSITIONS, LENGTH, SENSOR_POSITIONS, SolverConfig,
)
from budgeted_science.burgers.fitting import PredictionUnavailable
from budgeted_science.burgers.joint_fitting import fit_viscosity_amplitude
from budgeted_science.burgers.numerics import solve_candidate
from budgeted_science.burgers.observations import ObservationService
from budgeted_science.burgers.reference import ReferenceOracle, reference_values
from budgeted_science.burgers.scoring import score_planning


def records_for(nu=.23, amplitude=1.1, noise=0):
    service = ObservationService(
        ReferenceOracle(nu, initial_amplitude=amplitude), Ledger.shared(6), noise_std=noise,
    )
    return tuple(service.acquire(i)[0] for i in range(3))


def exact_predictor(nu, amplitude, records):
    return reference_values(nu, "calibration", [r.position for r in records],
                            initial_amplitude=amplitude).T


class TestAmplitudeNumerics(unittest.TestCase):
    def test_defaults_preserve_original_problem_and_credit(self):
        config = SolverConfig(.2)
        explicit = SolverConfig(.2, initial_amplitude=1)
        self.assertEqual(config.identity(), explicit.identity())
        self.assertEqual(solve_candidate(config).work_units, WORK_PER_CREDIT)
        np.testing.assert_array_equal(
            ReferenceOracle(.23).forecast_profile(),
            ReferenceOracle(.23, initial_amplitude=1).forecast_profile(),
        )

    def test_invalid_amplitude_is_rejected(self):
        for amplitude in (.79, 1.21, True, "1", np.nan, np.inf, None):
            with self.subTest(amplitude=amplitude):
                with self.assertRaises(ValueError):
                    SolverConfig(.2, initial_amplitude=amplitude)
                with self.assertRaises(ValueError):
                    ReferenceOracle(.2, initial_amplitude=amplitude)
                with self.assertRaises(ValueError):
                    reference_values(.2, "calibration", [1], initial_amplitude=amplitude)

    def test_reference_agreement_over_extended_parameter_box(self):
        positions = SENSOR_POSITIONS + FORECAST_POSITIONS
        for nu in (.1, .2, .3):
            for amplitude in (.8, 1, 1.2):
                for protocol in ("calibration", "forecast"):
                    with self.subTest(nu=nu, amplitude=amplitude, protocol=protocol):
                        a = reference_values(nu, protocol, positions, initial_amplitude=amplitude)
                        b = reference_values(nu, protocol, positions, initial_amplitude=amplitude,
                                             grid_size=2048)
                        self.assertLess(float(np.max(np.abs(a - b))), 1e-7)

    def test_initial_states_refinement_mass_and_energy_at_box_corners(self):
        for nu in (.1, .3):
            for amplitude in (.8, 1.2):
                for protocol in ("calibration", "forecast"):
                    truth = reference_values(nu, protocol, FORECAST_POSITIONS, [1],
                                             initial_amplitude=amplitude)[0]
                    errors = []
                    for n in (32, 64, 128):
                        config = SolverConfig(nu, n, protocol, initial_amplitude=amplitude)
                        result = solve_candidate(config)
                        self.assertEqual(result.status, "completed")
                        np.testing.assert_allclose(result.fields[0], config.amplitude * np.sin(config.positions))
                        np.testing.assert_allclose(result.fields.mean(axis=1), 0, atol=1e-12)
                        self.assertTrue(np.all(np.diff(np.mean(result.fields**2, axis=1)) <= 1e-12))
                        indices = np.rint(np.array(FORECAST_POSITIONS) / LENGTH * n).astype(int)
                        errors.append(float(np.sqrt(np.mean((result.fields[-1, indices] - truth)**2))))
                    self.assertGreater(errors[0], errors[1])
                    self.assertGreater(errors[1], errors[2])

    def test_amplitude_cache_identity_and_persistent_reuse(self):
        first = SolverConfig(.2, initial_amplitude=.9)
        second = SolverConfig(.2, initial_amplitude=1.1)
        self.assertNotEqual(cache_key(first), cache_key(second))
        adjacent = [SolverConfig(.2, protocol="forecast", initial_amplitude=a)
                    for a in (.8, np.nextafter(.8, 1))]
        self.assertNotEqual(cache_key(adjacent[0]), cache_key(adjacent[1]))
        with tempfile.TemporaryDirectory() as directory:
            service = SimulationService(Ledger.shared(10), SimulationCache(directory))
            a, b = service.run(first), service.run(second)
            self.assertFalse(np.array_equal(a.fields, b.fields))
            self.assertEqual(b.public()["initial_amplitude"], 1.1)
            self.assertEqual(service.run(second).charged_work_units, 0)
            fresh = SimulationService(Ledger.shared(10), SimulationCache(directory))
            with patch("budgeted_science.burgers.cache.solve_candidate", side_effect=AssertionError("cache miss")):
                replay = fresh.run(second)
            self.assertEqual(replay.charged_work_units, b.work_units)
            np.testing.assert_array_equal(replay.fields, b.fields)

    def test_amplitude_warm_and_cold_interruption_match(self):
        config = SolverConfig(.23, initial_amplitude=1.1)
        cache = SimulationCache()
        SimulationService(Ledger.unlimited(), cache).run(config)
        available = Fraction(192, WORK_PER_CREDIT)
        cold = SimulationService(Ledger.shared(available)).run(config)
        warm = SimulationService(Ledger.shared(available), cache).run(config)
        self.assertEqual(cold.status, "budget_exhausted")
        self.assertEqual(warm.charged_work_units, cold.charged_work_units)
        np.testing.assert_array_equal(warm.fields, cold.fields)

    def test_observation_amplitude_is_private_and_noise_stays_paired(self):
        a = ObservationService(ReferenceOracle(.23, initial_amplitude=.9), Ledger.shared(6), seed=7)
        b = ObservationService(ReferenceOracle(.23, initial_amplitude=1.1), Ledger.shared(6), seed=7)
        ra, rb = a.acquire(1)[0], b.acquire(1)[0]
        self.assertNotIn("initial_amplitude", rb.public())
        self.assertNotIn("viscosity", rb.public())
        np.testing.assert_allclose(
            np.array(ra.values) - ReferenceOracle(.23, initial_amplitude=.9).calibration_record(1),
            np.array(rb.values) - ReferenceOracle(.23, initial_amplitude=1.1).calibration_record(1),
            atol=1e-15,
        )
        before = b.ledger.status()
        self.assertEqual(b.retrieve(rb.record_id), rb)
        self.assertEqual(b.ledger.status(), before)
        with self.assertRaises(TypeError):
            b.acquire(1, initial_amplitude=1.1)

    def test_actual_profile_scoring_uses_target_amplitude_and_fixed_scale(self):
        truth = ReferenceOracle(.23, initial_amplitude=1.1).forecast_profile()
        self.assertEqual(score_planning(truth, .23, target_amplitude=1.1)["normalized_profile_rmse"], 0)
        self.assertAlmostEqual(score_planning(truth + .15, .23, target_amplitude=1.1)["normalized_profile_rmse"], .1)
        self.assertGreater(score_planning(truth, .23)["normalized_profile_rmse"], 0)
        candidate = solve_candidate(SolverConfig(.23, 64, "forecast", initial_amplitude=1.1))
        self.assertGreater(score_planning(candidate.forecast_profile(), .23,
                                         target_amplitude=1.1)["normalized_profile_rmse"], 0)


class TestJointFitting(unittest.TestCase):
    def test_reference_recoverability_is_only_an_offline_diagnostic(self):
        for nu, amplitude in ((.14, .9), (.2, 1), (.26, 1.1)):
            fit = fit_viscosity_amplitude(exact_predictor, records_for(nu, amplitude), max_evaluations=96)
            self.assertEqual(fit.status, "completed")
            self.assertLess(abs(fit.viscosity - nu), 1e-6)
            self.assertLess(abs(fit.initial_amplitude - amplitude), 1e-6)

    def test_finite_difference_evaluations_count_and_start_is_public(self):
        calls = []
        def predictor(nu, amplitude, records):
            calls.append((nu, amplitude))
            return exact_predictor(nu, amplitude, records)
        fit = fit_viscosity_amplitude(predictor, records_for(), max_evaluations=2)
        self.assertEqual(calls[0], (.2, 1.0))
        self.assertEqual(fit.evaluations, 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(fit.completed_evaluations, 2)
        self.assertEqual(fit.status, "evaluation_limit")

    def test_interruption_keeps_best_completed_fit(self):
        for exception, status in ((BudgetExceeded(), "budget_exhausted"),
                                  (PredictionUnavailable("numerical_failure"), "numerical_failure")):
            calls = []
            def predictor(nu, amplitude, records):
                calls.append((nu, amplitude))
                if len(calls) == 2:
                    raise exception
                return exact_predictor(nu, amplitude, records)
            fit = fit_viscosity_amplitude(predictor, records_for())
            self.assertEqual(fit.status, status)
            self.assertEqual((fit.viscosity, fit.initial_amplitude), calls[0])
            self.assertEqual(fit.completed_evaluations, 1)

    def test_no_completed_fit_does_not_fabricate_parameters(self):
        def predictor(nu, amplitude, records):
            raise BudgetExceeded()
        fit = fit_viscosity_amplitude(predictor, records_for())
        self.assertIsNone(fit.viscosity)
        self.assertIsNone(fit.initial_amplitude)
        self.assertIsNone(fit.mean_squared_residual)
        self.assertEqual(fit.status, "budget_exhausted")

    def test_bad_arguments_and_malformed_predictions(self):
        records = records_for()
        for limit in (0, True, 1.5):
            with self.assertRaises(ValueError):
                fit_viscosity_amplitude(exact_predictor, records, max_evaluations=limit)
        for bad in (None, (), records + records, [1]):
            with self.assertRaises(ValueError):
                fit_viscosity_amplitude(exact_predictor, bad)
        for malformed in (None, [[1], [1, 2]], [["bad"] * 5] * 3, [[True] * 5] * 3,
                          np.full((3, 5), np.nan), np.ones((1, 5))):
            fit = fit_viscosity_amplitude(lambda nu, a, rs: malformed, records)
            self.assertEqual(fit.status, "numerical_failure")
            self.assertIsNone(fit.viscosity)

    def test_metered_joint_fit_and_forecast_complete_within_twenty_credits(self):
        ledger = Ledger.shared(20)
        observations = ObservationService(ReferenceOracle(.23, initial_amplitude=1.1), ledger, seed=0)
        records = tuple(observations.acquire(i)[0] for i in range(3))
        simulations = SimulationService(ledger)
        def predictor(nu, amplitude, acquired):
            result = simulations.run(SolverConfig(nu, 64, initial_amplitude=amplitude))
            if result.status != "completed":
                raise PredictionUnavailable(result.status)
            return np.array([result.sensor_record(r.sensor_id) for r in acquired])
        fit = fit_viscosity_amplitude(predictor, records, max_evaluations=12)
        result = simulations.run(SolverConfig(fit.viscosity, 64, "forecast",
                                             initial_amplitude=fit.initial_amplitude))
        self.assertEqual(result.status, "completed")
        self.assertLessEqual(ledger.status()["total_spent"], 20)
        self.assertEqual(ledger.status()["spent"]["observation"], 6)
        self.assertGreater(ledger.status()["spent"]["compute"], 0)
        self.assertTrue(np.isfinite(score_planning(result.forecast_profile(), .23,
                                                  target_amplitude=1.1)["normalized_profile_rmse"]))


if __name__ == "__main__":
    unittest.main()

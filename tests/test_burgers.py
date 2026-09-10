"""Shared-foundation tests. Run after pip install -e .; no agents or network."""

from dataclasses import FrozenInstanceError
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.burgers.budget import BudgetExceeded, Ledger, WORK_PER_CREDIT
from budgeted_science.burgers.cache import SimulationCache, SimulationService, cache_key
from budgeted_science.burgers.config import (
    FORECAST_POSITIONS, LENGTH, RECORD_TIMES, SENSOR_POSITIONS, SolverConfig,
)
from budgeted_science.burgers.fitting import PredictionUnavailable, fit_viscosity
from budgeted_science.burgers.numerics import _rhs, solve_candidate
from budgeted_science.burgers.observations import ObservationService
from budgeted_science.burgers.reference import ReferenceOracle, reference_values
from budgeted_science.burgers.scoring import score_inference, score_planning, validate_profile
from budgeted_science.burgers.tools import FixedNumericalPredictor, InferenceTools, PlanningTools


def setup_episode(target=0.2, ledger=None, noise=0.01, seed=0, cache=None):
    ledger = ledger if ledger is not None else Ledger.shared(50)
    observations = ObservationService(ReferenceOracle(target), ledger, seed=seed, noise_std=noise)
    simulations = SimulationService(ledger, cache)
    return ledger, observations, simulations


class TestNumericalFoundation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {(nu, protocol, n): solve_candidate(SolverConfig(nu, n, protocol))
                    for nu in (0.1, 0.2, 0.3) for protocol in ("calibration", "forecast")
                    for n in (32, 64, 128)}

    def test_initial_conditions_and_recording(self):
        for result in self.runs.values():
            with self.subTest(config=result.config):
                self.assertEqual(result.status, "completed")
                np.testing.assert_array_equal(result.times, (0.0,) + RECORD_TIMES)
                np.testing.assert_allclose(result.fields[0], result.config.amplitude * np.sin(result.config.positions))
                self.assertEqual(result.work_units, result.config.resolution * result.rhs_evaluations)
                self.assertEqual(result.rhs_evaluations, 2 * result.completed_steps)
                self.assertTrue(np.all(np.isfinite(result.fields)))

    def test_mass_energy_and_maximum_bound(self):
        for result in self.runs.values():
            with self.subTest(config=result.config):
                mass = result.fields.mean(axis=1) * LENGTH
                np.testing.assert_allclose(mass, mass[0], atol=1e-12, rtol=0)
                energy = (result.fields**2).mean(axis=1) * LENGTH / 2
                self.assertTrue(np.all(np.diff(energy) <= 1e-12))
                self.assertLessEqual(float(np.abs(result.fields).max()), result.config.amplitude + 1e-12)

    def test_independent_reference_agreement(self):
        positions = SENSOR_POSITIONS + FORECAST_POSITIONS
        for nu in (0.1, 0.2, 0.3):
            for protocol in ("calibration", "forecast"):
                a = reference_values(nu, protocol, positions, grid_size=1024)
                b = reference_values(nu, protocol, positions, grid_size=2048)
                self.assertLess(float(np.abs(a - b).max()), 1e-7)

    def test_reference_initial_and_periodic_values(self):
        x = np.array(FORECAST_POSITIONS)
        for protocol, amplitude in (("calibration", 1.0), ("forecast", 1.5)):
            values = reference_values(0.2, protocol, x, [0, 1])
            np.testing.assert_allclose(values[0], amplitude * np.sin(x), atol=1e-14)
            np.testing.assert_allclose(values, reference_values(0.2, protocol, x + LENGTH, [0, 1]), atol=1e-11)

    def test_candidate_periodic_rhs_is_shift_invariant_and_conservative(self):
        u = np.random.default_rng(12).uniform(-1, 1, 32)
        rhs = _rhs(u, 0.2, LENGTH / 32)
        np.testing.assert_allclose(_rhs(np.roll(u, 7), 0.2, LENGTH / 32), np.roll(rhs, 7))
        self.assertAlmostEqual(float(rhs.sum()), 0, places=12)

    def test_error_decreases_with_grid_refinement(self):
        for nu in (0.1, 0.2, 0.3):
            for protocol in ("calibration", "forecast"):
                truth = reference_values(nu, protocol, FORECAST_POSITIONS, [1])[0]
                errors = []
                for n in (32, 64, 128):
                    result = self.runs[nu, protocol, n]
                    indices = np.rint(np.array(FORECAST_POSITIONS) / LENGTH * n).astype(int)
                    errors.append(float(np.sqrt(np.mean((result.fields[-1, indices] - truth)**2))))
                self.assertGreater(errors[0], errors[1])
                self.assertGreater(errors[1], errors[2])

    def test_canonical_credit_is_public_and_fixed(self):
        result = self.runs[0.2, "calibration", 64]
        self.assertEqual(result.work_units, WORK_PER_CREDIT)
        ledger = Ledger.shared(1)
        self.assertEqual(solve_candidate(result.config, ledger).status, "completed")
        self.assertEqual(ledger.status()["total_spent"], 1)

    def test_invalid_configs(self):
        for kwargs in ({"viscosity": float("nan")}, {"viscosity": True}, {"viscosity": 0.09},
                       {"viscosity": 0.31}, {"viscosity": "0.2"}, {"viscosity": 0.2, "resolution": 64.0},
                       {"viscosity": 0.2, "resolution": 256}, {"viscosity": 0.2, "protocol": "secret"},
                       {"viscosity": 0.2, "safety": 0}, {"viscosity": 0.2, "safety": 0.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                SolverConfig(**kwargs)

    def test_bad_reference_arguments(self):
        for kwargs in ({"grid_size": 1000}, {"positions": [float("nan")]}, {"times": [-1]},
                       {"times": [2]}, {"positions": []}):
            args = {"nu": 0.2, "protocol": "calibration", "positions": [0.5]}
            args.update(kwargs)
            with self.assertRaises(ValueError):
                reference_values(**args)


class TestAccountingAndCache(unittest.TestCase):
    def test_shared_pool_and_separate_caps(self):
        ledger = Ledger.shared(3)
        ledger.charge_observation(2)
        ledger.charge_work(WORK_PER_CREDIT)
        self.assertEqual(ledger.status()["total_spent"], 3)
        before = ledger.status()
        with self.assertRaises(BudgetExceeded):
            ledger.charge_work(1)
        self.assertEqual(before, ledger.status())
        separate = Ledger.separate(2, 1)
        separate.charge_work(WORK_PER_CREDIT)
        with self.assertRaises(BudgetExceeded):
            separate.charge_work(1)
        separate.charge_observation(2)
        self.assertEqual(separate.status()["total_spent"], 3)

    def test_invalid_budget_requests_do_not_mutate(self):
        for kwargs in ({"shared_credits": -1}, {"shared_credits": True}, {"shared_credits": float("inf")},
                       {"observation_credits": 1}, {"shared_credits": 3, "compute_credits": 1}):
            with self.assertRaises(ValueError):
                Ledger(**kwargs)
        ledger = Ledger.shared(1)
        for value in (-1, 0.5, True):
            with self.assertRaises(ValueError):
                ledger.charge_work(value)
        self.assertEqual(ledger.status()["total_spent"], 0)

    def test_interruption_charges_rhs_work_and_rejects_incomplete_predictions(self):
        ledger = Ledger.shared(Fraction(96, WORK_PER_CREDIT))
        result = solve_candidate(SolverConfig(0.2, 32), ledger)
        self.assertEqual(result.status, "budget_exhausted")
        self.assertEqual(result.rhs_evaluations, 3)
        self.assertEqual(result.completed_steps, 1)
        self.assertEqual(result.work_units, 96)
        self.assertEqual(result.charged_work_units, 96)
        self.assertEqual(result.times.tolist(), [0])
        with self.assertRaises(ValueError):
            result.sensor_record(0)
        with self.assertRaises(ValueError):
            result.forecast_profile()

    def test_numerical_failure_retains_work_charge(self):
        ledger = Ledger.shared(10)
        with patch("budgeted_science.burgers.numerics._rhs", side_effect=[np.zeros(32), FloatingPointError()]):
            result = solve_candidate(SolverConfig(0.2, 32), ledger)
        self.assertEqual(result.status, "numerical_failure")
        self.assertEqual(result.work_units, 64)
        self.assertEqual(ledger.work_units, 64)
        self.assertEqual(result.completed_steps, 0)

    def test_cache_identity_includes_all_tunable_settings(self):
        configs = [SolverConfig(0.2), SolverConfig(0.2, 32), SolverConfig(0.2, protocol="forecast"),
                   SolverConfig(0.2, safety=0.2), SolverConfig(np.nextafter(0.2, 0.3))]
        self.assertEqual(len({cache_key(c) for c in configs}), len(configs))

    def test_persistent_cache_and_episode_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SolverConfig(0.2)
            first = SimulationService(Ledger.shared(2), SimulationCache(directory))
            a = first.run(config)
            again = first.run(config)
            self.assertEqual(again.charged_work_units, 0)
            self.assertEqual(first.ledger.work_units, WORK_PER_CREDIT)
            second = SimulationService(Ledger.shared(2), SimulationCache(directory))
            with patch("budgeted_science.burgers.cache.solve_candidate", side_effect=AssertionError("cache miss")):
                b = second.run(config)
            self.assertEqual(b.charged_work_units, WORK_PER_CREDIT)
            np.testing.assert_array_equal(a.fields, b.fields)

    def test_warm_and_cold_budget_exhaustion_are_equivalent(self):
        config = SolverConfig(0.2)
        cache = SimulationCache()
        SimulationService(Ledger.unlimited(), cache).run(config)
        for available in (0, 1, 64, 192, 8192, WORK_PER_CREDIT - 32, WORK_PER_CREDIT):
            with self.subTest(available=available):
                cold = SimulationService(Ledger.shared(Fraction(available, WORK_PER_CREDIT)))
                warm = SimulationService(Ledger.shared(Fraction(available, WORK_PER_CREDIT)), cache)
                a, b = cold.run(config), warm.run(config)
                self.assertEqual(a.status, b.status)
                self.assertEqual(a.work_units, b.work_units)
                self.assertEqual(a.completed_steps, b.completed_steps)
                self.assertEqual(a.completed_time, b.completed_time)
                self.assertEqual(cold.ledger.status(), warm.ledger.status())
                np.testing.assert_array_equal(a.times, b.times)
                np.testing.assert_array_equal(a.fields, b.fields)

    def test_cache_cannot_be_changed_through_returned_arrays(self):
        service = SimulationService(Ledger.shared(5))
        result = service.run(SolverConfig(0.2))
        original = result.fields.copy()
        result.fields.setflags(write=True)
        result.fields[:] = 999
        np.testing.assert_array_equal(service.run(SolverConfig(0.2)).fields, original)

    def test_corrupted_cache_is_recomputed(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SolverConfig(0.2)
            path = Path(directory) / f"{cache_key(config)}.npz"
            path.write_bytes(b"not a numpy archive")
            service = SimulationService(Ledger.shared(5), SimulationCache(directory))
            result = service.run(config)
            self.assertEqual(result.status, "completed")
            self.assertIsNotNone(SimulationCache(directory).get(config))

    def test_truncated_zip_cache_is_recomputed(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SolverConfig(0.2)
            path = Path(directory) / f"{cache_key(config)}.npz"
            path.write_bytes(b"PK\x03\x04broken archive")
            result = SimulationService(Ledger.shared(5), SimulationCache(directory)).run(config)
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.charged_work_units, WORK_PER_CREDIT)


class TestObservations(unittest.TestCase):
    def test_record_shape_price_and_free_retrieval(self):
        ledger, observations, _ = setup_episode()
        record, = observations.acquire(1)
        self.assertEqual(record.times, RECORD_TIMES)
        self.assertEqual(record.position, SENSOR_POSITIONS[1])
        self.assertEqual(len(record.values), 5)
        self.assertEqual(ledger.status()["spent"]["observation"], 2)
        self.assertEqual(observations.retrieve(record.record_id), record)
        self.assertEqual(ledger.status()["total_spent"], 2)
        payload = record.public()
        self.assertEqual(set(payload), {"record_id", "sensor_id", "position", "times", "values", "noise_std", "replicate_index"})
        payload["values"] = (999,) * 5
        self.assertEqual(observations.retrieve(record.record_id), record)

    def test_repeats_are_paid_new_trials(self):
        ledger, observations, _ = setup_episode()
        a, b = observations.acquire(0, replicates=2)
        self.assertNotEqual(a.values, b.values)
        self.assertEqual((a.replicate_index, b.replicate_index), (0, 1))
        self.assertEqual(ledger.status()["total_spent"], 4)

    def test_noise_is_paired_across_order_and_batching(self):
        _, a, _ = setup_episode(seed=91)
        _, b, _ = setup_episode(seed=91)
        a.acquire(0)
        batch = a.acquire(2, 2)
        first, = b.acquire(2)
        b.acquire(1)
        second, = b.acquire(2)
        self.assertEqual(batch[0].values, first.values)
        self.assertEqual(batch[1].values, second.values)
        _, different, _ = setup_episode(seed=92)
        self.assertNotEqual(first.values, different.acquire(2)[0].values)

    def test_noise_free_records(self):
        _, observations, _ = setup_episode(noise=0)
        a, b = observations.acquire(1, 2)
        self.assertEqual(a.values, b.values)
        np.testing.assert_allclose(a.values, ReferenceOracle(0.2).calibration_record(1))

    def test_noise_distribution_sanity(self):
        ledger, observations, _ = setup_episode(ledger=Ledger.unlimited())
        records = observations.acquire(1, 500)
        errors = np.array([r.values for r in records]) - ReferenceOracle(0.2).calibration_record(1)
        self.assertLess(abs(errors.mean()), 0.001)
        self.assertGreater(errors.std(), 0.009)
        self.assertLess(errors.std(), 0.011)
        self.assertEqual(ledger.status()["total_spent"], 1000)

    def test_rejected_batch_does_not_consume_budget_or_rng_index(self):
        ledger, observations, _ = setup_episode(ledger=Ledger.shared(2))
        with self.assertRaises(BudgetExceeded):
            observations.acquire(0, 2)
        self.assertEqual(ledger.status()["total_spent"], 0)
        record, = observations.acquire(0)
        self.assertEqual(record.replicate_index, 0)
        _, fresh, _ = setup_episode()
        self.assertEqual(record.values, fresh.acquire(0)[0].values)

    def test_invalid_observation_requests(self):
        ledger, observations, _ = setup_episode()
        for sensor, count in ((-1, 1), (3, 1), (True, 1), (1, 0), (1, 1.5)):
            with self.assertRaises(ValueError):
                observations.acquire(sensor, count)
        with self.assertRaises(TypeError):
            observations.acquire(1, viscosity=0.2)
        with self.assertRaises(TypeError):
            observations.acquire(1, protocol="forecast")
        with self.assertRaises(ValueError):
            observations.retrieve("unpaid-record")
        self.assertEqual(ledger.status()["total_spent"], 0)


class TestFittingAndScoring(unittest.TestCase):
    @staticmethod
    def exact_predictor(nu, records):
        return reference_values(nu, "calibration", [r.position for r in records]).T

    def test_noise_free_reference_fit_recovers_viscosity(self):
        # Analytic-access recoverability diagnostic, not a matched tool baseline.
        for target in (0.14, 0.20, 0.26):
            _, observations, _ = setup_episode(target, noise=0)
            records = tuple(observations.acquire(i)[0] for i in range(3))
            result = fit_viscosity(self.exact_predictor, records)
            self.assertEqual(result.status, "completed")
            self.assertLess(abs(result.viscosity - target), 1e-6)

    def test_fit_preserves_best_complete_result_on_interruption(self):
        _, observations, _ = setup_episode(noise=0)
        records = observations.acquire(1)
        for exception, status in ((BudgetExceeded(), "budget_exhausted"),
                                  (PredictionUnavailable("numerical_failure"), "numerical_failure")):
            calls = []
            def predictor(nu, acquired):
                calls.append(nu)
                if len(calls) == 2:
                    raise exception
                return self.exact_predictor(nu, acquired)
            result = fit_viscosity(predictor, records)
            self.assertEqual(result.status, status)
            self.assertEqual(result.viscosity, calls[0])
            self.assertEqual(result.completed_evaluations, 1)
            self.assertEqual(result.evaluations, 2)

    def test_no_complete_fit_is_not_a_successful_submission(self):
        _, observations, _ = setup_episode()
        def predictor(nu, records):
            raise BudgetExceeded()
        result = fit_viscosity(predictor, observations.acquire(1))
        self.assertEqual(result.status, "budget_exhausted")
        self.assertIsNone(result.viscosity)
        self.assertIsNone(result.mean_squared_residual)

    def test_evaluation_limit_and_invalid_fit_inputs(self):
        _, observations, _ = setup_episode()
        records = observations.acquire(1)
        result = fit_viscosity(self.exact_predictor, records, max_evaluations=1)
        self.assertEqual(result.status, "evaluation_limit")
        self.assertEqual(result.evaluations, 1)
        for limit in (0, True, 1.1):
            with self.assertRaises(ValueError):
                fit_viscosity(self.exact_predictor, records, max_evaluations=limit)
        with self.assertRaises(ValueError):
            fit_viscosity(self.exact_predictor, records + records)
        invalid = fit_viscosity(lambda nu, records: np.full((1, 5), np.nan), records)
        self.assertEqual(invalid.status, "numerical_failure")

    def test_scoring_distinguishes_computed_and_reference_predictions(self):
        truth = ReferenceOracle(0.2).forecast_profile()
        self.assertEqual(score_planning(truth, 0.2)["normalized_profile_rmse"], 0)
        np.testing.assert_allclose(score_planning(truth + 0.15, 0.2)["normalized_profile_rmse"], 0.1)
        self.assertEqual(score_inference(0.2, 0.2)["normalized_reference_response_rmse"], 0)
        coarse = solve_candidate(SolverConfig(0.2, 32, "forecast")).forecast_profile()
        self.assertGreater(score_planning(coarse, 0.2)["normalized_profile_rmse"], 0)
        self.assertGreater(score_inference(0.25, 0.2)["absolute_viscosity_error"], 0)

    def test_malformed_predictor_preserves_best_completed_fit(self):
        _, observations, _ = setup_episode(noise=0)
        records = observations.acquire(1)
        for malformed in (None, [[1], [1, 2]], [["bad"] * 5], [[1j] * 5], [[True] * 5]):
            with self.subTest(malformed=malformed):
                predictor = iter([self.exact_predictor(0.1, records), malformed])
                result = fit_viscosity(lambda nu, acquired: next(predictor), records)
                self.assertEqual(result.status, "numerical_failure")
                self.assertEqual(result.viscosity, 0.1)
                self.assertEqual(result.completed_evaluations, 1)

    def test_large_finite_profile_has_finite_score(self):
        error = score_planning([1e308] * 16, 0.2)["normalized_profile_rmse"]
        self.assertTrue(np.isfinite(error))
        self.assertAlmostEqual(error / 1e308, 1 / 1.5)

    def test_invalid_submissions(self):
        for value in ([], [0] * 15, [[0] * 16], [np.nan] * 16, [np.inf] * 16,
                      ["0"] * 16, [True] * 16, [1j] * 16, None):
            with self.assertRaises(ValueError):
                validate_profile(value)
        for value in (True, "0.2", float("nan"), 0.09, 0.31, None):
            with self.assertRaises(ValueError):
                score_inference(value, 0.2)


class TestToolContracts(unittest.TestCase):
    def test_planning_flow_and_private_evaluation(self):
        ledger, observations, simulations = setup_episode(noise=0)
        tools = PlanningTools(observations, simulations, ledger)
        ids = [tools.observe(2)[0]["record_id"]]
        fitted = tools.fit(ids, resolution=32, max_evaluations=12)
        self.assertIsNotNone(fitted["viscosity"])
        output = tools.simulate(fitted["viscosity"], 64, "forecast")
        self.assertEqual(output["status"], "completed")
        indices = np.rint(np.array(FORECAST_POSITIONS) / LENGTH * 64).astype(int)
        profile = np.array(output["fields"])[-1, indices]
        acknowledgement = tools.submit(profile)
        self.assertEqual(acknowledgement, {"status": "submitted", "kind": "forecast_profile"})
        self.assertEqual(len(tools.submission), 16)
        self.assertGreater(ledger.status()["spent"]["compute"], 0)
        self.assertNotIn("score", json.dumps(acknowledgement))

    def test_inference_only_exposes_registered_fixed_predictors(self):
        ledger, observations, simulations = setup_episode(ledger=Ledger.separate(8, 30), noise=0)
        model = FixedNumericalPredictor(simulations, 32)
        registry = {"coarse_fixture": model}
        tools = InferenceTools(observations, registry, ledger)
        registry.clear()
        record_id = tools.observe(1)[0]["record_id"]
        fitted = tools.fit("coarse_fixture", [record_id], max_evaluations=6)
        self.assertIsNotNone(fitted["viscosity"])
        output = tools.predict("coarse_fixture", fitted["viscosity"])
        self.assertEqual(output["resolution"], 32)
        self.assertFalse(hasattr(tools, "simulate"))
        self.assertFalse(hasattr(tools, "reference"))
        before = ledger.status()
        for action in ("simulate", "reference", "score", "_model", "__dict__", "_observations"):
            with self.assertRaises(ValueError):
                tools.dispatch(action)
        with self.assertRaises(TypeError):
            tools.predict("coarse_fixture", 0.2, resolution=128)
        with self.assertRaises(ValueError):
            tools.predict("unregistered", 0.2)
        with self.assertRaises(FrozenInstanceError):
            model.resolution = 128
        self.assertEqual(before, ledger.status())
        self.assertEqual(tools.submit(0.2), {"status": "submitted", "kind": "viscosity"})

    def test_fitting_multiple_records_does_not_bypass_compute_accounting(self):
        ledger, observations, simulations = setup_episode()
        records = observations.acquire(1, 2)
        tools = PlanningTools(observations, simulations, ledger)
        result = tools.fit([r.record_id for r in records], resolution=32, max_evaluations=1)
        expected_work = solve_candidate(SolverConfig(0.1, 32)).work_units
        self.assertEqual(result["evaluations"], 1)
        self.assertEqual(ledger.work_units, expected_work)
        self.assertEqual(ledger.status()["spent"]["observation"], 4)

    def test_fitting_obeys_tight_compute_cap(self):
        ledger, observations, simulations = setup_episode(ledger=Ledger.separate(2, 0.001))
        tools = PlanningTools(observations, simulations, ledger)
        record = tools.observe(0)[0]
        result = tools.fit([record["record_id"]], resolution=32)
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertIsNone(result["viscosity"])
        self.assertLessEqual(ledger.status()["spent"]["compute"], 0.001)

    def test_bad_tool_arguments_do_not_spend(self):
        ledger, observations, simulations = setup_episode()
        tools = PlanningTools(observations, simulations, ledger)
        for request in (("simulate", {"viscosity": float("nan")}),
                        ("observe", {"sensor_id": 4}),
                        ("fit", {"record_ids": ["unpaid"]}),
                        ("submit", {"profile": [0] * 15})):
            with self.assertRaises(ValueError):
                tools.dispatch(request[0], **request[1])
        self.assertEqual(ledger.status()["total_spent"], 0)
        self.assertIsNone(tools.submission)

    def test_episode_ledgers_cannot_be_mixed(self):
        ledger, observations, simulations = setup_episode()
        with self.assertRaises(ValueError):
            PlanningTools(observations, simulations, Ledger.shared(5))
        with self.assertRaises(ValueError):
            PlanningTools(observations, SimulationService(Ledger.shared(5)), ledger)


if __name__ == "__main__":
    unittest.main()

"""Harder toy and classical baseline checks; no API or credential access."""

from dataclasses import replace
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.integrate import solve_ivp

from budgeted_science.resource_planning.config import Config, harder_config
from budgeted_science.resource_planning.environment import Episode, _rhs, _solve_high, _solve_low
from budgeted_science.resource_planning.checkpoint import export_episode, restore_episode
from budgeted_science.resource_planning.emulator import Calibration
from budgeted_science.resource_planning.local_policy import LocalFit, run_local_policy
from budgeted_science.resource_planning.harder_pilot import aggregate, select_budget, worker, render

MID = [1., .08, 1.4]


class HarderEnvironmentTests(unittest.TestCase):
    def test_explicit_v2_leaves_v1_defaults_and_public_schema_unchanged(self):
        self.assertEqual(Config().tolerance, .1)
        self.assertNotIn('observation_noise_fraction', Config().public())
        c = harder_config(32)
        self.assertEqual(c.tolerance, .05)
        self.assertEqual(c.budget, 32)
        self.assertEqual(Config.from_public(c.public()), c)
        self.assertEqual(c.observation_noise_fraction, .01)

    def test_noise_validation(self):
        for value in (-.1, .11, float('nan'), True, 'noise'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Config(observation_noise_fraction=value)
        for seed in (-1, True, .5):
            with self.assertRaises(ValueError):
                Episode(MID, noise_seed=seed)

    def test_free_observations_are_noisy_initial_conditions_are_exact(self):
        clean = Episode(MID)
        noisy = Episode(MID, harder_config(), noise_seed=123)
        a, b = clean.tools.evidence()['observations'], noisy.tools.evidence()['observations']
        self.assertEqual([r['value'] for r in a[:2]], [r['value'] for r in b[:2]])
        self.assertNotEqual([r['value'] for r in a[2:]], [r['value'] for r in b[2:]])
        self.assertEqual([r['noise_std'] for r in b], [0, 0, .1, .05])
        self.assertNotIn('noise_seed', noisy.tools.public_config)

    def test_noise_is_order_independent_and_retrieval_is_not_a_new_sample(self):
        a, b = [Episode(MID, harder_config(), noise_seed=21) for _ in range(2)]
        ax = a.tools.measure_target('x', 3)
        ay = a.tools.measure_target('y', 5)
        by = b.tools.measure_target('y', 5)
        bx = b.tools.measure_target('x', 3)
        self.assertEqual(ax['value'], bx['value'])
        self.assertEqual(ay['value'], by['value'])
        replay = a.tools.measure_target('x', 3)
        self.assertEqual(replay['charge'], 0)
        self.assertEqual(replay['value'], ax['value'])
        c = Episode(MID, harder_config(), noise_seed=22)
        self.assertNotEqual(c.tools.measure_target('x', 3)['value'], ax['value'])

    def test_noisy_checkpoint_preserves_future_noise_without_reference_rerun(self):
        a = Episode(MID, harder_config(), noise_seed=987)
        a.tools.simulate_low(MID)
        saved = json.loads(json.dumps(export_episode(a)))
        with patch('budgeted_science.resource_planning.environment._solve_high', side_effect=AssertionError('unpaid')):
            b = restore_episode(saved)
            self.assertEqual(a.tools.measure_target('x', 2.5), b.tools.measure_target('x', 2.5))

    def test_high_solver_agrees_with_independent_radau_at_wide_corners(self):
        config = harder_config()
        for theta in product(*config.bounds):
            high = _solve_high(theta, config).sample(config.working_times)
            radau = solve_ivp(_rhs, (0,8), config.initial, args=(theta,), method='Radau',
                              rtol=1e-11, atol=1e-13, t_eval=config.working_times)
            self.assertTrue(radau.success)
            self.assertLess(np.max(np.abs(high-radau.y.T)), 1e-6)

    def test_new_tolerance_boundary_and_budget(self):
        e = Episode(MID, harder_config(24))
        e.tools.submit([1.05, .084, 1.47])
        self.assertTrue(e.evaluate()['success'])
        e = Episode(MID, harder_config(24))
        e.tools.submit([1.051, .08, 1.4])
        self.assertFalse(e.evaluate()['success'])


class HarderFittingTests(unittest.TestCase):
    def evidence(self):
        e = Episode(MID, harder_config(), noise_seed=0)
        for theta in ([1.,.08,1.4], [1.1,.08,1.4], [1.,.09,1.4], [1.,.08,1.6]):
            e.tools.simulate_low(theta)
        e.tools.simulate_high(MID)
        e.tools.measure_target('x', 3)
        return e

    def test_local_analysis_never_calls_solver(self):
        e = self.evidence()
        with patch('budgeted_science.resource_planning.environment._solve_high', side_effect=AssertionError('unpaid')), \
             patch('budgeted_science.resource_planning.environment._solve_low', side_effect=AssertionError('unpaid')):
            fitted = LocalFit(e.tools.evidence(), e.tools.public_config)
            self.assertEqual(len(fitted.proposals()), 3)
            self.assertTrue(fitted.measurement())
            self.assertEqual(len(fitted.biases), 1)

    def test_noise_aware_gp_likelihood_matches_direct_covariance_calculation(self):
        e = self.evidence()
        evidence, c = e.tools.evidence(), e.tools.public_config
        fit = Calibration(evidence['simulations'], evidence['observations'], c['bounds'], c['initial'],
                          c['working_times'], noise_fraction=.01)
        means = [np.zeros((1,16)), np.zeros((1,16))]
        variances = [np.array([.2]), np.array([.3])]
        expected = 0
        for j, obs in enumerate(fit.obs):
            indices = np.array([o[0] for o in obs])
            values = np.array([o[1] for o in obs])
            cov = variances[j][0] * fit.temporal[np.ix_(indices,indices)]
            cov += np.eye(len(indices)) * (.01**2 + fit.settings.likelihood_jitter)
            expected -= .5 * (np.linalg.slogdet(cov)[1] + values @ np.linalg.solve(cov,values))
        self.assertAlmostEqual(float(fit.likelihood(means,variances)[0]), expected, places=10)

    def test_budgeted_baseline_replays_and_uses_only_public_solver_calls(self):
        e = Episode(MID, harder_config(), noise_seed=11)
        access = {'inside': False, 'low': 0, 'high': 0}
        class Tools:
            @property
            def public_config(self): return e.tools.public_config
            def evidence(self): return e.tools.evidence()
            def get_status(self): return e.tools.get_status()
            def measure_target(self,*args): return e.tools.measure_target(*args)
            def submit(self,*args): return e.tools.submit(*args)
            def simulate_low(self,*args):
                access['inside'] = True
                try: return e.tools.simulate_low(*args)
                finally: access['inside'] = False
            def simulate_high(self,*args):
                access['inside'] = True
                try: return e.tools.simulate_high(*args)
                finally: access['inside'] = False
        def guarded(fn, key):
            def call(*args):
                self.assertTrue(access['inside'])
                access[key] += 1
                return fn(*args)
            return call
        with patch('budgeted_science.resource_planning.environment._solve_high', side_effect=guarded(_solve_high,'high')), \
             patch('budgeted_science.resource_planning.environment._solve_low', side_effect=guarded(_solve_low,'low')):
            run_local_policy(Tools())
        self.assertEqual((access['low'],access['high']), (20,1))
        self.assertEqual(e.evaluate()['spent'],40)
        b = Episode(MID, harder_config(), noise_seed=11)
        run_local_policy(b.tools)
        self.assertEqual(e.evaluate(),b.evaluate())

    def test_local_method_passes_original_easy_instance(self):
        e = Episode([1.0300545275430546,.08625698437171549,1.1162226223635487])
        run_local_policy(e.tools)
        self.assertTrue(e.evaluate()['success'])

    def test_lower_budget_caps_and_invalid_small_budget(self):
        for budget in (24,32):
            e = Episode(MID, harder_config(budget))
            run_local_policy(e.tools)
            self.assertEqual(e.evaluate()['spent'],budget)
        with self.assertRaises(ValueError):
            run_local_policy(Episode(MID, harder_config(20)).tools)


class HarderExperimentTests(unittest.TestCase):
    def test_development_selection_never_needs_evaluation(self):
        rows = [{'budget':b,'policy':'local','evaluation':{'success': b>=32}} for b in (40,32,24) for _ in range(16)]
        self.assertEqual(select_budget(rows),24)
        rows[0]['evaluation']['success'] = False
        rows[1]['evaluation']['success'] = False
        self.assertEqual(select_budget(rows),40)

    def test_worker_records_complete_reproducible_paid_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            result = worker({'budget':24,'policy':'local','target_seed':5000,'noise_replicate':0},temp)
            self.assertEqual(result['termination'],'submitted')
            self.assertEqual(result['evaluation']['spent'],24)
            root = Path(result['path'])
            self.assertTrue((root/'events.jsonl').is_file())
            self.assertTrue(list((root/'numerical').glob('*.json')))
            self.assertEqual(json.loads((root/'result.json').read_text())['scientific_status'], result['scientific_status'])


if __name__ == '__main__':
    unittest.main()

"""CPU-only numerical, artifact, policy-isolation and offline-replay checks."""

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.heat_workflow import experiment as exp
from budgeted_science.heat_workflow import numerics as num


class NumericsTests(unittest.TestCase):
    def test_invalid_configurations(self):
        for args in ({"n": True}, {"n": 4}, {"n": 258}, {"relaxation": 0},
                     {"relaxation": 1.2}, {"update_tolerance": float('nan')},
                     {"max_iterations": 0}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                num.Config(**args)
        with self.assertRaises(ValueError):
            num.Problem(top=float('inf'))

    def test_constant_boundary_reference(self):
        self.assertAlmostEqual(num.reference_mean(num.Problem(2, 2, 2, 2)), 2, places=12)

    def test_reference_convergence_and_grid_study(self):
        result = num.validate()
        self.assertLess(result['fourier_128_256_difference'], 1e-12)
        self.assertLess(result['grid_study'][-1]['relative_error'], 0.0002)

    def test_boundary_and_maximum_principle(self):
        field, _ = num.solve_direct(num.Problem(), 17)
        np.testing.assert_array_equal(field[1:-1, -1], 1)
        np.testing.assert_array_equal(field[1:-1, 0], 0)
        self.assertGreaterEqual(field.min(), 0)
        self.assertLessEqual(field.max(), 1)
        self.assertEqual(field[0, -1], 0.5)

    def test_independent_matrix_and_jacobi_agree(self):
        problem = num.Problem(top=1.2, bottom=0.1, left=0.4, right=0.2)
        field, info = num.solve_jacobi(problem, num.Config(n=17, update_tolerance=1e-12))
        other, direct = num.solve_direct(problem, 17)
        np.testing.assert_allclose(field, other, atol=1e-9, rtol=0)
        self.assertEqual(info['grid_point_iterations'], 17**2 * info['iterations'])
        self.assertLess(direct['residual_rms'], 1e-10)

    def test_patch_integration_affine_field(self):
        grid = np.linspace(0, 1, 17)
        field = 3 + 2*grid[:, None] + 4*grid[None, :]
        self.assertAlmostEqual(num.patch_mean(field), 3 + 2*0.2 + 4*0.7, places=12)

    def test_patch_rejects_invalid_fields_and_regions(self):
        for field in (np.zeros((3, 4)), np.full((5, 5), np.nan)):
            with self.assertRaises(ValueError):
                num.patch_mean(field)
        with self.assertRaises(ValueError):
            num.patch_mean(np.zeros((5, 5)), (0, 0.5, 0.1, 0.3))

    def test_termination_is_explicit(self):
        _, info = num.solve_jacobi(num.Problem(), num.Config(max_iterations=1))
        self.assertEqual(info['status'], 'iteration_limit')
        _, info = num.solve_jacobi(num.Problem(), num.Config(), deadline_seconds=0)
        self.assertEqual(info['status'], 'timeout')

    def test_literal_analysis_and_axis_error(self):
        field, _ = num.solve_direct(num.Problem(), 33)
        for transpose in (False, True):
            value = num.analyze_owned_source(num.analysis_source(transpose), field)
            self.assertEqual(value, num.patch_mean(field.T if transpose else field))
        self.assertGreater(abs(num.patch_mean(field.T)-num.patch_mean(field))/num.patch_mean(field), 0.8)

    def test_arbitrary_script_is_not_executed(self):
        with self.assertRaises(ValueError):
            num.analyze_owned_source("raise RuntimeError('must not run')", np.zeros((5, 5)))

    def test_scoring_boundary_and_nonfinite(self):
        self.assertEqual(num.classify(1.125, 1, 0.125)['verdict'], 'ACCEPT')
        self.assertEqual(num.classify(1.1251, 1, 0.125)['verdict'], 'REJECT')
        for a, b in ((float('nan'), 1), (1, 0), (1, float('inf'))):
            with self.assertRaises(ValueError):
                num.classify(a, b)


class ControlTests(unittest.TestCase):
    def study(self):
        return {"intended": exp.public_specification(), "reported_Q": 0.31,
                "run_config": {"boundaries": asdict(num.Problem(left=0.5)),
                               "numerical": asdict(num.Config())},
                "analysis_source": num.analysis_source(True)}

    def test_refinement_preserves_boundary_and_analysis(self):
        field, _ = num.solve_direct(num.Problem(left=0.5), 17)
        with patch.object(exp, 'solve_jacobi', return_value=(field, {'status': 'update_threshold_reached'})) as solve:
            result = exp.control(self.study(), 'refinement_only')
        self.assertEqual(solve.call_args.args[0].left, 0.5)
        self.assertEqual(solve.call_args.args[1].n, 65)
        self.assertEqual(result['estimate'], num.patch_mean(field.T))

    def test_reconstruction_uses_only_intended_problem(self):
        with patch.object(num, 'reference_mean', side_effect=AssertionError('unpaid reference')), \
             patch.object(exp, 'analyze_owned_source', side_effect=AssertionError('wrong analysis')):
            result = exp.control(self.study(), 'independent_reconstruction')
        self.assertEqual(result['status'], 'completed')
        self.assertAlmostEqual(result['estimate'], 0.31208, places=4)
        self.assertTrue(all(c['boundaries']['left'] == 0 for c in result['calls']))

    def test_failed_refinement_cannot_supply_verdict(self):
        field = num.initial_field(num.Problem(), 17)
        with patch.object(exp, 'solve_jacobi', return_value=(field, {'status': 'timeout'})):
            result = exp.control(self.study(), 'refinement_only')
        self.assertIsNone(result['verdict'])
        self.assertEqual(result['status'], 'incomplete')


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.path = exp.run(Path(cls.temporary.name))
        cls.summary = json.loads((cls.path / 'summary.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_four_studies_eight_controls(self):
        self.assertEqual(self.summary['status'], 'complete')
        self.assertEqual(len(self.summary['cases']), 4)
        self.assertEqual(len(self.summary['results']), 8)
        correct = {method: sum(r['correct'] for r in self.summary['results'] if r['method'] == method)
                   for method in ('refinement_only', 'independent_reconstruction')}
        self.assertEqual(correct, {'refinement_only': 2, 'independent_reconstruction': 4})
        self.assertEqual(self.summary['api_dollars'], 0)

    def test_printed_claim_is_executed_script_output(self):
        for case in self.summary['cases']:
            path = self.path / 'studies' / case['id'] / 'public'
            source = (path / 'analysis.py').read_text()
            with np.load(path / 'trajectory.npz', allow_pickle=False) as data:
                value = num.analyze_owned_source(source, data['T'])
            self.assertEqual(float(f'{value:.10g}'), case['reported_Q'])
            self.assertIn(f"{case['reported_Q']:.10g}", (path / 'report.md').read_text())

    def test_public_folders_exclude_evaluator_labels(self):
        for case in self.summary['cases']:
            path = self.path / 'studies' / case['id'] / 'public'
            for file in path.iterdir():
                if file.suffix == '.npz':
                    continue
                content = file.read_text()
                for prohibited in ('reference_mean', 'relative_error', 'premature_stopping', 'boundary_mismatch', 'truth'):
                    self.assertNotIn(prohibited, content)

    def test_analysis_script_runs_standalone(self):
        case = self.summary['cases'][2]
        path = self.path / 'studies' / case['id'] / 'public' / 'analysis.py'
        result = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, text=True, check=True)
        self.assertEqual(float(f"{json.loads(result.stdout)['Q']:.10g}"), case['reported_Q'])

    def test_offline_report_is_identical_without_execution(self):
        before = (self.path/'report.md').read_bytes()
        with patch.object(exp, 'solve_direct', side_effect=AssertionError('solver called')), \
             patch.object(exp, 'solve_jacobi', side_effect=AssertionError('solver called')), \
             patch.object(exp, 'analyze_owned_source', side_effect=AssertionError('code executed')):
            exp.render(self.path)
        self.assertEqual(before, (self.path/'report.md').read_bytes())

    def test_tampered_copy_is_rejected(self):
        import shutil
        copy = self.path.parent / 'tampered'
        shutil.copytree(self.path, copy)
        (copy/'summary.json').write_text('{}')
        with self.assertRaises(ValueError):
            exp.render(copy)

    def test_interruption_preserves_partial_run_and_unique_directory(self):
        with patch.object(exp, 'validate', side_effect=RuntimeError('synthetic interruption')):
            path = exp.run(self.path.parent)
        self.assertNotEqual(path, self.path)
        summary = json.loads((path/'summary.json').read_text())
        self.assertEqual(summary['status'], 'incomplete')
        self.assertEqual(summary['unattempted_controls'], 8)
        self.assertTrue((path/'events.jsonl').exists())
        exp.render(path)


if __name__ == '__main__':
    unittest.main()

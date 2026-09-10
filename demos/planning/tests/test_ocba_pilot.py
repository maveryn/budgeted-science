"""Run: python -m unittest discover -s demos/planning/tests -v"""

import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ocba_pilot import (COSTS, ORIGINAL, POLICIES, Moments, QuadratureOracle,
                        SamplingOracle, constrained_targets, ocba_cost_weights,
                        run_quadrature, run_sampling, scenarios, trapezoid, wilson)


class TestPilot(unittest.TestCase):
    def test_reference_integrals(self):
        expected = (1.1, 0.5536577478043857, 0.44814353912664284)
        for c, target in zip(ORIGINAL, expected):
            self.assertAlmostEqual(c.integral(), target, places=12)
            # Independent dense midpoint quadrature rather than the same erf formula.
            n = 32768
            midpoint = sum(c.value((j + 0.5) / n) for j in range(n)) / n
            self.assertAlmostEqual(midpoint, target, places=8)

    def test_online_moments(self):
        m = Moments()
        for y in (1, 2, 3):
            m.add(y)
        self.assertEqual(m.mean, 2)
        self.assertEqual(m.variance, 1)

    def test_equal_cost_classic_ocba_identity(self):
        means, v = [0, 1, 2], [4, 9, 16]
        w = ocba_cost_weights(means, v, [1, 1, 1])
        self.assertAlmostEqual(w[1] / w[2], (9 / 1) / (16 / 4))
        self.assertAlmostEqual(w[0], math.sqrt(4 * (w[1] ** 2 / 9 + w[2] ** 2 / 16)))

    def test_two_arm_unequal_cost_optimum(self):
        # Minimizing variance v0/n0+v1/n1 under c0*n0+c1*n1=B gives
        # n0/n1 = sqrt(v0*c1/(v1*c0)). This catches credit/count confusion.
        w = ocba_cost_weights([0, 1], [4, 9], [1, 4])
        counts_ratio = (w[0] / 1) / (w[1] / 4)
        self.assertAlmostEqual(counts_ratio, math.sqrt(4 * 4 / 9))

    def test_ties_zero_variance_and_permutation(self):
        w = ocba_cost_weights([1, 1, 1], [0, 0, 0], COSTS)
        self.assertTrue(all(math.isfinite(x) and x > 0 for x in w))
        self.assertAlmostEqual(sum(w), 1)
        a = ocba_cost_weights([0, 1, 2], [2, 3, 4], [1, 2, 3])
        b = ocba_cost_weights([2, 0, 1], [4, 2, 3], [3, 1, 2])
        for x, y in zip(b, [a[2], a[0], a[1]]):
            self.assertAlmostEqual(x, y)

    def test_sunk_cost_targets(self):
        t = constrained_targets([0.1, 0.2, 0.7], [20, 3, 3], 40)
        self.assertAlmostEqual(sum(t), 40)
        self.assertTrue(all(a >= b for a, b in zip(t, [20, 3, 3])))
        self.assertAlmostEqual(t[1] / t[2], 2 / 7)
        with self.assertRaises(ValueError):
            constrained_targets([0.5, 0.5], [10, 10], 19)

    def test_cache_and_refinement_charges(self):
        oracle = QuadratureOracle()
        trapezoid(oracle, 2, 4)
        self.assertEqual(oracle.spent, 2 + 5 * 2)
        trapezoid(oracle, 2, 8)
        self.assertEqual(oracle.spent, 2 + 9 * 2)
        trapezoid(oracle, 2, 8)
        self.assertEqual(oracle.spent, 20)

    def test_budget_rejection_is_atomic(self):
        o = SamplingOracle(scenarios()[0], 0, 2)
        with self.assertRaises(ValueError):
            o.sample(0)
        self.assertEqual(o.spent, 0)
        self.assertEqual(o.counts, [0, 0, 0])
        q = QuadratureOracle(budget=2)
        with self.assertRaises(ValueError):
            q.value(0, 0.5)
        self.assertEqual(q.spent, 0)
        self.assertEqual(q.cache, {})

    def test_shared_random_streams(self):
        a = SamplingOracle(scenarios()[0], 9, 120)
        b = SamplingOracle(scenarios()[0], 9, 120)
        a.sample(1)
        self.assertEqual(a.sample(0), b.sample(0))
        self.assertEqual(a.sample(2), b.sample(2))

    def test_complete_runs_and_accounting(self):
        for scenario in scenarios():
            for policy in POLICIES:
                r = run_sampling(scenario, 3, 120, policy, trace=True)
                self.assertEqual(r["spent"], 120)
                self.assertEqual(r["spent"], 6 + sum(n * c for n, c in zip(r["counts"], COSTS)))
                self.assertEqual(sum(x["charge"] for x in r["trace"]), 120)
                self.assertTrue(all(n >= 5 for n in r["counts"]))
                self.assertTrue(math.isfinite(r["mae"]))
                self.assertGreaterEqual(r["regret"], 0)
                self.assertEqual(r, run_sampling(scenario, 3, 120, policy, trace=True))

    def test_quadrature_budget_and_results(self):
        equal = run_quadrature("equal_cost")
        adaptive = run_quadrature("adaptive_refinement")
        self.assertEqual(equal["intervals"], [32, 32, 16])
        self.assertEqual(adaptive["intervals"], [8, 32, 32])
        self.assertLessEqual(equal["spent"], 120)
        self.assertLessEqual(adaptive["spent"], 120)
        self.assertAlmostEqual(equal["mae"], 0.006573022366698156, places=12)
        self.assertAlmostEqual(adaptive["mae"], 0.000010367940143659235, places=12)

    def test_wilson_boundaries(self):
        low, high = wilson(0, 100)
        self.assertAlmostEqual(low, 0)
        self.assertGreater(high, 0)
        low, high = wilson(100, 100)
        self.assertLess(low, 1)
        self.assertAlmostEqual(high, 1)


if __name__ == "__main__":
    unittest.main()

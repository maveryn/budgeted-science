"""An explicit sparse-data ambiguity, not a budgeted-policy baseline."""
import unittest
import numpy as np
from budgeted_science.resource_planning.config import Config
from budgeted_science.resource_planning.environment import _solve_high


class TestSparseIdentifiability(unittest.TestCase):
    def test_one_additional_reading_does_not_guarantee_uniqueness(self):
        first=np.array([1., .08, 1.4])
        second=np.array([.9525528757705348, .06719520228468322, 1.247988786038443])
        observations=[]
        for theta in (first,second):
            values=_solve_high(theta,Config()).sample([1.,4.])
            observations.append([values[0,0],values[0,1],values[1,1]])
        # x(1), y(1), and even y(4) agree at the production solver's accuracy.
        np.testing.assert_allclose(observations[0],observations[1],atol=1e-7,rtol=0)
        self.assertGreater(abs(first[1]-second[1])/first[1],.1)
        # This establishes non-uniqueness, NOT impossibility of meeting the 10%
        # tolerance: the two acceptable-answer boxes can still overlap.


if __name__ == '__main__':
    unittest.main()

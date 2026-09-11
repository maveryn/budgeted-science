"""Evaluator-side Cole-Hopf/Fourier reference; not an agent tool.

For u0=A*sin(x), psi0=exp(A*(cos(x)-1)/(2*nu)); psi solves the heat
equation and u=-2*nu*psi_x/psi. The constant shift avoids large exponentials.
See https://math.nyu.edu/~tabak/PDEs/The_Burgers-Equation.pdf, section 6.3.
The formula is public and a lawful shortcut for a future coding-enabled track.
"""

import numpy as np

from .config import (
    LENGTH, RECORD_TIMES, FORECAST_POSITIONS, SENSOR_POSITIONS,
    viscosity, integer, protocol_amplitude, sensor_index, initial_amplitude_value,
)


def reference_values(nu, protocol, positions, times=RECORD_TIMES, *, grid_size=1024,
                     initial_amplitude=1.0):
    nu = viscosity(nu)
    amplitude = initial_amplitude_value(initial_amplitude) * protocol_amplitude(protocol)
    n = integer(grid_size, "grid_size", 32)
    if n & (n - 1):
        raise ValueError("reference grid_size must be a power of two")
    x = np.asarray(positions, dtype=float)
    ts = np.asarray(times, dtype=float)
    if x.ndim != 1 or x.size == 0 or not np.all(np.isfinite(x)):
        raise ValueError("positions must be a nonempty finite vector")
    if ts.ndim != 1 or ts.size == 0 or not np.all(np.isfinite(ts)) or np.any(ts < 0) or np.any(ts > 1):
        raise ValueError("times must be a nonempty vector in [0, 1]")
    x = np.mod(x, LENGTH)
    grid = np.arange(n) * LENGTH / n
    initial = np.exp(amplitude * (np.cos(grid) - 1) / (2 * nu))
    coefficients = np.fft.fft(initial)
    modes = np.fft.fftfreq(n, d=LENGTH / n) * 2 * np.pi
    # Direct Fourier evaluation avoids introducing a linear-interpolation error
    # into reference observations or comparisons across differently sized grids.
    basis = np.exp(1j * np.outer(modes, x)) / n
    values = []
    for t in ts:
        if t == 0:
            values.append(amplitude * np.sin(x))
            continue
        h = coefficients * np.exp(-nu * modes**2 * t)
        phi = (h @ basis).real
        dphi = ((1j * modes * h) @ basis).real
        if np.any(phi <= 0) or not np.all(np.isfinite(phi)):
            raise FloatingPointError("reference transformation lost positivity")
        value = -2 * nu * dphi / phi
        if not np.all(np.isfinite(value)):
            raise FloatingPointError("nonfinite reference")
        values.append(value)
    return np.array(values)


class ReferenceOracle:
    """Private fixed-target component owned by the trusted experiment harness."""

    def __init__(self, target_viscosity, *, grid_size=1024, initial_amplitude=1.0):
        self._target = viscosity(target_viscosity)
        self._initial_amplitude = initial_amplitude_value(initial_amplitude)
        n = integer(grid_size, "grid_size", 32)
        if n & (n - 1):
            raise ValueError("reference grid_size must be a power of two")
        self._grid_size = n
        self._records = {}

    def calibration_record(self, sensor_id):
        sensor_id = sensor_index(sensor_id)
        if sensor_id not in self._records:
            self._records[sensor_id] = reference_values(
                self._target, "calibration", [SENSOR_POSITIONS[sensor_id]], grid_size=self._grid_size,
                initial_amplitude=self._initial_amplitude,
            )[:, 0]
        return self._records[sensor_id].copy()

    def forecast_profile(self):
        return reference_values(
            self._target, "forecast", FORECAST_POSITIONS, [1.0], grid_size=self._grid_size,
            initial_amplitude=self._initial_amplitude,
        )[0]

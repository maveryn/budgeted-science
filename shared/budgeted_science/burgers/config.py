"""The deliberately small, dimensionless v1 task family."""

from dataclasses import dataclass
import math
from numbers import Integral, Real

import numpy as np

LENGTH = 2 * math.pi
VISCOSITY_BOUNDS = (0.1, 0.3)
INITIAL_AMPLITUDE_BOUNDS = (0.8, 1.2)
RESOLUTIONS = (32, 64, 128)
RECORD_TIMES = (0.2, 0.4, 0.6, 0.8, 1.0)
AMPLITUDES = {"calibration": 1.0, "forecast": 1.5}
SENSOR_POSITIONS = (math.pi / 4, math.pi / 2, 3 * math.pi / 4)
FORECAST_POSITIONS = tuple((j + 0.5) * LENGTH / 16 for j in range(16))
SCORE_SCALE = 1.5
SOLVER_VERSION = "rusanov-centered-diffusion-ssprk2-v1"
REFERENCE_VERSION = "periodic-cole-hopf-fourier-v1"


def finite_real(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return value


def integer(value, name, minimum=0):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def viscosity(value):
    value = finite_real(value, "viscosity")
    if not VISCOSITY_BOUNDS[0] <= value <= VISCOSITY_BOUNDS[1]:
        raise ValueError("viscosity must be in [0.1, 0.3]")
    return value


def protocol_amplitude(protocol):
    if not isinstance(protocol, str) or protocol not in AMPLITUDES:
        raise ValueError("protocol must be calibration or forecast")
    return AMPLITUDES[protocol]


def initial_amplitude_value(value):
    value = finite_real(value, "initial_amplitude")
    if not INITIAL_AMPLITUDE_BOUNDS[0] <= value <= INITIAL_AMPLITUDE_BOUNDS[1]:
        raise ValueError("initial_amplitude must be in [0.8, 1.2]")
    return value


def sensor_index(sensor_id):
    sensor_id = integer(sensor_id, "sensor_id")
    if sensor_id >= len(SENSOR_POSITIONS):
        raise ValueError("sensor_id must be 0, 1, or 2")
    return sensor_id


@dataclass(frozen=True)
class SolverConfig:
    viscosity: float
    resolution: int = 64
    protocol: str = "calibration"
    safety: float = 0.4
    initial_amplitude: float = 1.0

    def __post_init__(self):
        object.__setattr__(self, "viscosity", viscosity(self.viscosity))
        n = integer(self.resolution, "resolution")
        if n not in RESOLUTIONS:
            raise ValueError(f"resolution must be one of {RESOLUTIONS}")
        object.__setattr__(self, "resolution", n)
        protocol_amplitude(self.protocol)
        object.__setattr__(self, "initial_amplitude", initial_amplitude_value(self.initial_amplitude))
        safety = finite_real(self.safety, "safety")
        if not 0 < safety <= 0.4:
            raise ValueError("safety must be in (0, 0.4]")
        object.__setattr__(self, "safety", safety)

    @property
    def amplitude(self):
        return self.initial_amplitude * protocol_amplitude(self.protocol)

    @property
    def positions(self):
        return np.arange(self.resolution) * LENGTH / self.resolution

    def identity(self):
        """Full deterministic configuration; float.hex avoids cache quantization."""
        identity = {
            "solver_version": SOLVER_VERSION,
            "viscosity": self.viscosity.hex(),
            "resolution": self.resolution,
            "protocol": self.protocol,
            "amplitude": self.amplitude.hex(),
            "safety": self.safety.hex(),
            "length": LENGTH.hex(),
            "boundary": "periodic",
            "record_times": [t.hex() for t in RECORD_TIMES],
            "initial_condition": "amplitude*sin(x)",
            "representation": "uniform-grid-values",
        }
        # Preserve existing A=1 cache keys. Record other A values explicitly:
        # multiplication by the forecast factor can round adjacent A values to
        # the same effective amplitude, but their public configurations differ.
        if self.initial_amplitude != 1.0:
            identity["initial_amplitude"] = self.initial_amplitude.hex()
        return identity

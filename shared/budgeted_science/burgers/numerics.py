"""Conservative grid-value Rusanov flux, centered diffusion, SSP-RK2."""

from dataclasses import dataclass, replace
from time import perf_counter

import numpy as np

from .budget import BudgetExceeded, WORK_PER_CREDIT
from .config import LENGTH, RECORD_TIMES, FORECAST_POSITIONS, SENSOR_POSITIONS, SolverConfig, sensor_index


@dataclass(frozen=True)
class SimulationResult:
    config: SolverConfig
    times: np.ndarray
    fields: np.ndarray
    work_units: int
    rhs_evaluations: int
    completed_steps: int
    completed_time: float
    status: str
    message: str
    wall_seconds: float
    charged_work_units: int = 0

    def __post_init__(self):
        for name in ("times", "fields"):
            array = np.array(getattr(self, name), dtype=float, copy=True)
            array.setflags(write=False)
            object.__setattr__(self, name, array)

    def copy(self, **changes):
        return replace(self, **changes)

    def _require_complete(self):
        if self.status != "completed":
            raise ValueError("incomplete simulation cannot supply a complete prediction")

    def sensor_record(self, sensor_id):
        self._require_complete()
        i = sensor_index(sensor_id)
        index = round(SENSOR_POSITIONS[i] / LENGTH * self.config.resolution)
        return self.fields[1:, index].copy()

    def forecast_profile(self):
        self._require_complete()
        if self.config.protocol != "forecast":
            raise ValueError("forecast profile requires the forecast protocol")
        indices = np.rint(np.array(FORECAST_POSITIONS) / LENGTH * self.config.resolution).astype(int)
        return self.fields[-1, indices].copy()

    def public(self):
        return {
            "viscosity": self.config.viscosity, "resolution": self.config.resolution,
            "protocol": self.config.protocol, "positions": self.config.positions.tolist(),
            "times": self.times.tolist(), "fields": self.fields.tolist(),
            "status": self.status, "message": self.message,
            "work_units": self.work_units, "charged_work_units": self.charged_work_units,
            "charged_credits": self.charged_work_units / WORK_PER_CREDIT,
            "rhs_evaluations": self.rhs_evaluations, "completed_steps": self.completed_steps,
            "completed_time": self.completed_time, "wall_seconds": self.wall_seconds,
        }


def _rhs(u, nu, dx):
    right, left = np.roll(u, -1), np.roll(u, 1)
    speed = np.maximum(np.abs(u), np.abs(right))
    flux = 0.25 * (u * u + right * right) - 0.5 * speed * (right - u)
    return -(flux - np.roll(flux, 1)) / dx + nu * (right - 2 * u + left) / dx**2


def solve_candidate(config, ledger=None):
    if not isinstance(config, SolverConfig):
        raise ValueError("config must be SolverConfig")
    start = perf_counter()
    n, nu = config.resolution, config.viscosity
    dx = LENGTH / n
    u = config.amplitude * np.sin(config.positions)
    times, fields = [0.0], [u.copy()]
    t, evaluations, steps = 0.0, 0, 0
    charged_before = ledger.work_units if ledger is not None else 0

    def result(status, message):
        return SimulationResult(
            config, np.array(times), np.array(fields), n * evaluations, evaluations,
            steps, t, status, message, perf_counter() - start,
            0 if ledger is None else ledger.work_units - charged_before,
        )

    def evaluate(v):
        nonlocal evaluations
        if ledger is not None:
            ledger.charge_work(n)
        evaluations += 1
        # Each RHS attempt is one fixed work-proxy unit per grid point, including
        # an attempt that encounters a floating-point error; it is not a FLOP count.
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            out = _rhs(v, nu, dx)
        if not np.all(np.isfinite(out)):
            raise FloatingPointError("nonfinite right-hand side")
        return out

    try:
        for end in RECORD_TIMES:
            while t < end - 1e-14:
                dt = min(config.safety / (np.max(np.abs(u)) / dx + 2 * nu / dx**2), end - t)
                if not np.isfinite(dt) or dt <= 0 or t + dt == t:
                    raise FloatingPointError("time step cannot advance")
                with np.errstate(over="raise", invalid="raise", divide="raise"):
                    stage = u + dt * evaluate(u)
                    candidate = 0.5 * u + 0.5 * (stage + dt * evaluate(stage))
                if not np.all(np.isfinite(candidate)):
                    raise FloatingPointError("nonfinite state")
                u = candidate
                t += dt
                steps += 1
            t = end
            times.append(end)
            fields.append(u.copy())
    except BudgetExceeded:
        return result("budget_exhausted", "Cannot fund the next RHS evaluation; prior work remains charged.")
    except (FloatingPointError, OverflowError):
        return result("numerical_failure", "Numerical evaluation failed; attempted work remains charged.")
    return result("completed", "Completed all requested recording times.")

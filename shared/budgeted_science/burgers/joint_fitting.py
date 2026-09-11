"""Opt-in two-parameter least-squares helper; no reference or target access.

This is an ordinary numerical optimizer callable from Python, not a new agent
action or a resumable fitting protocol. Its injected predictor owns metering.
"""

from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import least_squares

from .budget import BudgetExceeded
from .config import INITIAL_AMPLITUDE_BOUNDS, VISCOSITY_BOUNDS, integer
from .fitting import PredictionUnavailable
from .observations import ObservationRecord


@dataclass(frozen=True)
class JointFitResult:
    viscosity: float | None
    initial_amplitude: float | None
    mean_squared_residual: float | None
    evaluations: int
    completed_evaluations: int
    status: str

    def public(self):
        return asdict(self)


class _EvaluationLimit(RuntimeError):
    pass


def fit_viscosity_amplitude(predictor, records, *, max_evaluations=48):
    """Fit predictor(nu, amplitude, records) -> (number of records, 5).

    Start at the public box midpoint, not a private target-dependent guess.
    Count ALL predictor calls, including finite-difference Jacobian evaluations
    that scipy's nfev does not include. Retain the best completed prediction if
    the evaluation allowance or scientific budget interrupts optimization.
    """
    limit = integer(max_evaluations, "max_evaluations", 1)
    if not callable(predictor):
        raise ValueError("predictor must be callable")
    try:
        records = tuple(records)
    except TypeError as exc:
        raise ValueError("fit requires acquired observation records") from exc
    if not records or any(not isinstance(r, ObservationRecord) for r in records):
        raise ValueError("fit requires acquired observation records")
    if len({r.record_id for r in records}) != len(records):
        raise ValueError("do not duplicate an acquired record")
    if len({r.noise_std for r in records}) != 1:
        raise ValueError("joint fitting requires equal declared noise levels")
    observed = np.array([r.values for r in records])
    bounds = np.array((VISCOSITY_BOUNDS, INITIAL_AMPLITUDE_BOUNDS)).T
    lower, upper = bounds
    best, best_loss = None, None
    calls, completed = 0, 0

    def residual(unit_parameters):
        nonlocal best, best_loss, calls, completed
        if calls >= limit:
            raise _EvaluationLimit
        calls += 1
        nu, amplitude = lower + unit_parameters * (upper - lower)
        output = predictor(float(nu), float(amplitude), records)
        try:
            predicted = np.asarray(output)
        except (TypeError, ValueError) as exc:
            raise PredictionUnavailable("numerical_failure") from exc
        if (predicted.shape != observed.shape or predicted.dtype.kind not in "iuf"
                or not np.all(np.isfinite(predicted))):
            raise PredictionUnavailable("numerical_failure")
        with np.errstate(over="raise", invalid="raise"):
            error = predicted.astype(float) - observed
            loss = float(np.mean(error**2))
        if not np.isfinite(loss):
            raise PredictionUnavailable("numerical_failure")
        completed += 1
        if best_loss is None or loss < best_loss:
            best, best_loss = (float(nu), float(amplitude)), loss
        return error.ravel()

    status = "completed"
    try:
        optimized = least_squares(
            residual, [0.5, 0.5], bounds=(0.0, 1.0), diff_step=1e-4,
            ftol=1e-10, xtol=1e-10, gtol=1e-10, max_nfev=limit,
        )
        if not optimized.success:
            status = "evaluation_limit"
    except _EvaluationLimit:
        status = "evaluation_limit"
    except BudgetExceeded:
        status = "budget_exhausted"
    except PredictionUnavailable as exc:
        status = exc.status
    except (FloatingPointError, OverflowError):
        status = "numerical_failure"
    return JointFitResult(
        None if best is None else best[0], None if best is None else best[1],
        best_loss, calls, completed, status,
    )

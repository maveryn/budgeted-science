"""One-parameter numerical fitting; no reference or target access is imported."""

from dataclasses import asdict, dataclass
from typing import Callable, Sequence

import numpy as np
from scipy.optimize import minimize_scalar

from .budget import BudgetExceeded
from .config import VISCOSITY_BOUNDS, integer
from .observations import ObservationRecord


class PredictionUnavailable(RuntimeError):
    def __init__(self, status):
        if status not in ("budget_exhausted", "numerical_failure"):
            raise ValueError("unknown prediction failure status")
        self.status = status
        super().__init__(status)


@dataclass(frozen=True)
class FitResult:
    viscosity: float | None
    mean_squared_residual: float | None
    evaluations: int
    completed_evaluations: int
    status: str

    def public(self):
        return asdict(self)


class _EvaluationLimit(RuntimeError):
    pass


def fit_viscosity(predictor: Callable, records: Sequence[ObservationRecord], *, max_evaluations=32):
    """Predictor(nu, records) returns one five-value row per acquired trial.

    Predictors own scientific accounting. Repeated numerical outputs may be
    reused; distinct noisy experimental records remain distinct evidence. All
    v1 records must have the same declared noise standard deviation.
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
        raise ValueError("v1 fitting requires equal declared noise levels")
    observed = np.array([r.values for r in records])
    best_nu, best_loss = None, None
    calls, completed = 0, 0

    def objective(nu):
        nonlocal best_nu, best_loss, calls, completed
        if calls >= limit:
            raise _EvaluationLimit
        calls += 1
        output = predictor(float(nu), records)
        try:
            predicted = np.asarray(output)
        except (TypeError, ValueError) as exc:
            raise PredictionUnavailable("numerical_failure") from exc
        if (predicted.shape != observed.shape or predicted.dtype.kind not in "iuf"
                or not np.all(np.isfinite(predicted))):
            raise PredictionUnavailable("numerical_failure")
        predicted = predicted.astype(float)
        with np.errstate(over="raise", invalid="raise"):
            loss = float(np.mean((predicted - observed)**2))
        if not np.isfinite(loss):
            raise PredictionUnavailable("numerical_failure")
        completed += 1
        if best_loss is None or loss < best_loss:
            best_nu, best_loss = float(nu), loss
        return loss

    status = "completed"
    try:
        # max_evaluations bounds actual predictor calls, including boundaries.
        objective(VISCOSITY_BOUNDS[0])
        objective(VISCOSITY_BOUNDS[1])
        optimized = minimize_scalar(objective, bounds=VISCOSITY_BOUNDS, method="bounded",
                                    options={"xatol": 1e-10, "maxiter": limit})
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
    return FitResult(best_nu, best_loss, calls, completed, status)

"""Two small trusted-tool facades, not arbitrary-code security sandboxes."""

from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from .config import SolverConfig, viscosity
from .fitting import PredictionUnavailable, fit_viscosity
from .scoring import validate_profile


def _record_predictions(result, records):
    if result.status != "completed":
        raise PredictionUnavailable(result.status)
    return np.array([result.sensor_record(r.sensor_id) for r in records])


class _CommonTools:
    _actions = ("observe", "record", "budget", "fit", "submit")

    def __init__(self, observations, ledger):
        if observations.ledger is not ledger:
            raise ValueError("observations and tools must share one episode ledger")
        self._observations, self._ledger = observations, ledger
        self._submission = None

    def observe(self, sensor_id, replicates=1):
        return [record.public() for record in self._observations.acquire(sensor_id, replicates)]

    def record(self, record_id):
        return self._observations.retrieve(record_id).public()

    def budget(self):
        return self._ledger.status()

    def dispatch(self, action, **arguments):
        if not isinstance(action, str) or action not in self._actions:
            raise ValueError("action is not available in this task")
        return getattr(self, action)(**arguments)

    @property
    def submission(self):
        """The caller's own immutable answer, for the separate trusted evaluator."""
        return self._submission


class PlanningTools(_CommonTools):
    _actions = _CommonTools._actions + ("simulate",)

    def __init__(self, observations, simulations, ledger):
        super().__init__(observations, ledger)
        if simulations.ledger is not ledger:
            raise ValueError("simulations and tools must share one episode ledger")
        self._simulations = simulations

    def simulate(self, viscosity, resolution=64, protocol="calibration"):
        return self._simulations.run(SolverConfig(viscosity, resolution, protocol)).public()

    def fit(self, record_ids, resolution=64, max_evaluations=32):
        SolverConfig(0.2, resolution)
        records = self._observations.resolve(record_ids)

        def predictor(nu, acquired):
            return _record_predictions(self._simulations.run(SolverConfig(nu, resolution)), acquired)

        return fit_viscosity(predictor, records, max_evaluations=max_evaluations).public()

    def submit(self, profile):
        self._submission = tuple(validate_profile(profile))
        return {"status": "submitted", "kind": "forecast_profile"}


@dataclass(frozen=True)
class FixedNumericalPredictor:
    """Resolution-locked contract fixture, NOT a trained complementary surrogate."""
    simulations: object
    resolution: int

    def __post_init__(self):
        SolverConfig(0.2, self.resolution)

    def predict(self, viscosity, protocol="calibration"):
        return self.simulations.run(SolverConfig(viscosity, self.resolution, protocol))


class InferenceTools(_CommonTools):
    _actions = _CommonTools._actions + ("predict",)

    def __init__(self, observations, predictors, ledger):
        super().__init__(observations, ledger)
        if not predictors or any(not isinstance(k, str) or not k for k in predictors):
            raise ValueError("register named fixed predictors")
        for model in predictors.values():
            if not isinstance(model, FixedNumericalPredictor) or model.simulations.ledger is not ledger:
                raise ValueError("v1 fixtures must use the episode ledger")
        self._predictors = MappingProxyType(dict(predictors))

    def _model(self, model_id):
        if not isinstance(model_id, str) or model_id not in self._predictors:
            raise ValueError("unknown model_id")
        return self._predictors[model_id]

    def predict(self, model_id, viscosity, protocol="calibration"):
        return self._model(model_id).predict(viscosity, protocol).public()

    def fit(self, model_id, record_ids, max_evaluations=32):
        model = self._model(model_id)
        records = self._observations.resolve(record_ids)

        def predictor(nu, acquired):
            return _record_predictions(model.predict(nu), acquired)

        return fit_viscosity(predictor, records, max_evaluations=max_evaluations).public()

    def submit(self, viscosity_estimate):
        self._submission = viscosity(viscosity_estimate)
        return {"status": "submitted", "kind": "viscosity"}

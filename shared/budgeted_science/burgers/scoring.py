"""Private, noise-free evaluation, never returned by an episode's tools."""

import numpy as np

from .config import FORECAST_POSITIONS, SCORE_SCALE, viscosity
from .reference import ReferenceOracle, reference_values


def validate_profile(profile):
    try:
        values = np.asarray(profile)
    except (TypeError, ValueError) as exc:
        raise ValueError("submit a finite numeric vector of length 16") from exc
    if values.shape != (16,) or values.dtype.kind not in "iuf" or not np.all(np.isfinite(values)):
        raise ValueError("submit a finite numeric vector of length 16")
    return values.astype(float, copy=True)


def profile_error(profile, truth):
    values, target = validate_profile(profile), validate_profile(truth)
    try:
        with np.errstate(over="raise", invalid="raise"):
            # Scale before subtraction and use stable RMS to avoid overflow
            # merely from squaring a very large but finite submitted value.
            residual = values / SCORE_SCALE - target / SCORE_SCALE
            magnitude = float(np.max(np.abs(residual)))
            error = 0.0 if magnitude == 0 else magnitude * float(np.sqrt(np.mean((residual / magnitude)**2)))
    except FloatingPointError as exc:
        raise ValueError("submission produces nonfinite error") from exc
    if not np.isfinite(error):
        raise ValueError("submission produces nonfinite error")
    return error


def score_planning(profile, target_viscosity):
    values = validate_profile(profile)
    truth = ReferenceOracle(target_viscosity).forecast_profile()
    return {"normalized_profile_rmse": profile_error(values, truth)}


def score_inference(estimated_viscosity, target_viscosity):
    estimated, target = viscosity(estimated_viscosity), viscosity(target_viscosity)
    prediction = reference_values(estimated, "forecast", FORECAST_POSITIONS, [1.0])[0]
    truth = ReferenceOracle(target).forecast_profile()
    return {"normalized_reference_response_rmse": profile_error(prediction, truth),
            "absolute_viscosity_error": abs(estimated - target)}
